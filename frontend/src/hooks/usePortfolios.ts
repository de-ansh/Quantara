import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';

export interface PortfolioPosition {
    ticker: string;
    weight: number; // 0-1
    shares?: number;
    cost_basis?: number;
}

/** Units of one AMFI mutual fund scheme. */
export interface PortfolioFund {
    scheme_code: number;
    name: string;
    units: number;
    cost_basis: number; // per unit
}

export interface Portfolio {
    id: number;
    name: string;
    description: string | null;
    initial_investment: number;
    positions: PortfolioPosition[];
    funds: PortfolioFund[];
    created_at: string;
    updated_at: string;
}

export type PortfolioInput = Pick<Portfolio, 'name' | 'description' | 'initial_investment' | 'positions'> & {
    funds?: Omit<PortfolioFund, 'name'>[];
};

export interface FundMatch {
    scheme_code: number;
    name: string;
    nav: number;
}

/** The AMFI scheme each imported row means (null: no single scheme fits, or a listed ETF that stays a stock). */
export const matchFunds = async (rows: { isin: string | null; name: string }[]) =>
    (await apiClient.post<{ matches: (FundMatch | null)[] }>('/portfolio/funds/match', { funds: rows })).data.matches;

const KEY = ['portfolios'];

export const usePortfolios = () => {
    return useQuery({
        queryKey: KEY,
        queryFn: async () => {
            const { data } = await apiClient.get<{ portfolios: Portfolio[] }>('/portfolio/');
            return data.portfolios;
        },
    });
};

/** Create when `id` is absent, otherwise replace the portfolio's fields and positions. */
export const useSavePortfolio = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, ...body }: PortfolioInput & { id?: number }) => {
            const { data } = id
                ? await apiClient.put<Portfolio>(`/portfolio/${id}`, body)
                : await apiClient.post<Portfolio>('/portfolio/', body);
            return data;
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
    });
};

export const useDeletePortfolio = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            await apiClient.delete(`/portfolio/${id}`);
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
    });
};

export interface HoldingPerformance {
    kind: 'stock' | 'fund'; // a fund's ticker is its AMFI scheme code and its price the NAV
    ticker: string;
    name: string;
    sector: string | null;
    currency: 'USD' | 'INR';
    shares: number;
    avg_cost: number;
    price: number | null;
    market_value: number | null;
    cost_value: number;
    unrealized_pnl: number | null;
    unrealized_pnl_pct: number | null;
    day_change: number | null;
    weight_by_value: number | null;
    price_date?: string | null; // funds: the day of the NAV used
}

export interface CurrencyTotals {
    currency: 'USD' | 'INR';
    market_value: number;
    cost_value: number;
    unrealized_pnl: number;
    unrealized_pnl_pct: number | null;
    day_change: number;
    sector_allocation: Record<string, number>;
}

export interface PortfolioPerformance {
    portfolio_id: number;
    holdings: HoldingPerformance[];
    totals: CurrencyTotals[];
    prices_as_of: string | null;
    weight_only_tickers: string[];
}

export const usePortfolioPerformance = (id: number) => {
    return useQuery({
        queryKey: ['portfolioPerformance', id],
        queryFn: async () => (await apiClient.get<PortfolioPerformance>(`/portfolio/${id}/performance`)).data,
        refetchInterval: 5 * 60 * 1000,
    });
};

export interface HoldingUpdate {
    kind: 'signal' | 'alert' | 'transcript' | 'results' | 'verdict' | 'event';
    day: string; // YYYY-MM-DD
    text: string;
    tone: 'good' | 'bad' | 'neutral';
    upcoming: boolean;
}

export interface PortfolioUpdates {
    portfolio_id: number;
    name: string;
    performance: PortfolioPerformance;
    updates: Record<string, HoldingUpdate[]>; // by ticker; holdings with nothing new are absent
}

/** Every portfolio valued now, with the last week's news and the next two weeks' events per holding. */
export const usePortfolioUpdates = () => {
    return useQuery({
        queryKey: ['portfolioUpdates'],
        queryFn: async () => (await apiClient.get<{ portfolios: PortfolioUpdates[] }>('/portfolio/updates')).data.portfolios,
        refetchInterval: 5 * 60 * 1000,
    });
};

export interface BalanceFlag {
    kind: 'stock' | 'sector' | 'mix' | 'verdict' | 'elsewhere';
    title: string;
    detail: string;
    currency: 'USD' | 'INR';
    ticker: string | null;
    amount: number | null; // how much to sell to get back under the limit
}

export interface TargetMix {
    equity: number;
    debt: number;
    cash: number;
    gold: number;
    max_stock: number; // one company, % of the portfolio
    max_sector: number;
    is_default?: boolean; // not saved yet: the risk profile's starting point
}

export interface Trade {
    action: 'sell' | 'add';
    asset_class: string;
    amount: number;
    currency: 'USD' | 'INR';
    ticker: string | null;
    name: string | null;
    reason: string;
    gain: number | null; // profit (negative: loss) the sale realises, before tax
    held_in?: string[]; // all-portfolios view: the portfolios holding it
}

export interface PortfolioBalance {
    portfolio_id: number | null; // null: all portfolios together
    flags: BalanceFlag[];
    mix: Record<string, Record<string, number>>; // currency -> equity / debt / cash / gold -> %
    target: TargetMix;
    plan: Trade[]; // rupee holdings only
    risk_level: string | null;
}

/** Flags against the target mix, and the sells and adds that get back to it; `newMoney` is invested first. */
export const usePortfolioBalance = (id: number | 'all', newMoney = 0) => {
    return useQuery({
        queryKey: ['portfolioBalance', id, newMoney],
        queryFn: async () => (await apiClient.get<PortfolioBalance>(id === 'all' ? '/portfolio/balance' : `/portfolio/${id}/balance`,
            { params: newMoney ? { new_money: newMoney } : {} })).data,
        placeholderData: prev => prev, // keep the plan on screen while a new amount loads
    });
};

/** Save the target mix (null: back to the risk profile's starting point); every portfolio's check uses it. */
export const useSaveTargetMix = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (target: TargetMix | null) =>
            (target ? await apiClient.put<TargetMix>('/portfolio/target-mix', target) : await apiClient.delete<TargetMix>('/portfolio/target-mix')).data,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['portfolioBalance'] }),
    });
};
