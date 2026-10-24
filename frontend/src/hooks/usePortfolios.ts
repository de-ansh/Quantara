import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';

export interface PortfolioPosition {
    ticker: string;
    weight: number; // 0-1
    shares?: number;
    cost_basis?: number;
}

export interface Portfolio {
    id: number;
    name: string;
    description: string | null;
    initial_investment: number;
    positions: PortfolioPosition[];
    created_at: string;
    updated_at: string;
}

export type PortfolioInput = Pick<Portfolio, 'name' | 'description' | 'initial_investment' | 'positions'>;

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
