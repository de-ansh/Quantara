import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import type { SignalEvent } from '@/types';
import type { ApiSignal } from '@/types/api';

/** Mirrors the backend's signal_score: insider/institutional signals only fire on net buying. */
const direction = (s: ApiSignal): SignalEvent['type'] => {
    const m = s.metadata ?? {};
    if (m.direction === 'bearish' || (m.sentiment_change ?? 0) < 0) return 'BEARISH';
    if (m.direction === 'bullish' || s.signal_type.endsWith('_buying') || (m.sentiment_change ?? 0) > 0) return 'BULLISH';
    return 'NEUTRAL';
};

const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** A signal in plain words (same wording as the dashboard's portfolio updates). */
export const signalSummary = (s: ApiSignal): string => {
    const m = s.metadata ?? {};
    const net = num(m.net_pct_of_company), pledged = num(m.pledged_pct_of_promoter), change = num(m.change_pp);
    if (s.signal_type === 'large_deal' && net !== null)
        return `Bulk/block deals: net ${net >= 0 ? 'buying' : 'selling'} of ${Math.abs(net).toFixed(2)}% of the company`;
    if (s.signal_type === 'promoter_pledge' && pledged !== null)
        return `Promoters have pledged ${pledged.toFixed(1)}% of their shares`;
    if (s.signal_type === 'promoter_holding_change' && change !== null)
        return `Promoter stake ${change >= 0 ? 'up' : 'down'} ${Math.abs(change).toFixed(2)} points this quarter`;
    const words = s.signal_type.replace(/_/g, ' ').toLowerCase();
    return words.charAt(0).toUpperCase() + words.slice(1);
};

interface SignalsListResponse {
    signals: ApiSignal[];
    total_count: number;
}

export const useSignals = (options = {}) => {
    return useQuery({
        queryKey: ['signals'],
        refetchInterval: 5 * 60_000, // the server collects signals hourly
        queryFn: async () => {
            const { data } = await apiClient.get<SignalsListResponse>('/signals');

            // Transform backend signals to frontend SignalEvent format
            return data.signals.map(s => ({
                // Signals are dated events (earnings day, filing day), so a time of day would always read 00:00
                time: new Date(s.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
                type: direction(s),
                ticker: s.ticker,
                summary: signalSummary(s),
                text: `${s.ticker}: ${signalSummary(s)}`,
            }));
        },
        ...options
    });
};
