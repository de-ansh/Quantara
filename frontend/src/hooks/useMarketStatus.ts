import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';

export interface MarketRegion {
    name: string;
    index_name: string;
    index_value: number;
    index_change: string; // "+1.12%"
    vix: number;
    status: 'OPEN' | 'CLOSED';
    secondary_index_name: string | null;
    secondary_index_value: number | null;
    secondary_index_change: string | null;
}

export interface MarketStatus {
    vix: { value: number; change_percent: number; status: string };
    alerts: { id: number; time: string; type: string; text: string }[];
    us_market: MarketRegion | null;
    india_market: MarketRegion | null;
}

/**
 * One cached market snapshot for the whole app (header ticker and dashboard read the same numbers).
 * The server refreshes quotes every few minutes, so polling faster would only show the same values.
 */
export const useMarketStatus = (enabled = true) =>
    useQuery({
        queryKey: ['marketStatus'],
        queryFn: async () => (await apiClient.get<MarketStatus>('/market/status')).data,
        enabled,
        refetchInterval: 60_000,
    });
