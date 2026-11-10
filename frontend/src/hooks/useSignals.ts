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

interface SignalsListResponse {
    signals: ApiSignal[];
    total_count: number;
}

export const useSignals = (options = {}) => {
    return useQuery({
        queryKey: ['signals'],
        queryFn: async () => {
            const { data } = await apiClient.get<SignalsListResponse>('/signals');

            // Transform backend signals to frontend SignalEvent format
            return data.signals.map(s => ({
                // Signals are dated events (earnings day, filing day), so a time of day would always read 00:00
                time: new Date(s.timestamp).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }),
                type: direction(s),
                text: `${s.ticker}: ${s.signal_type.replace(/_/g, ' ').toUpperCase()}. Strength: ${Math.round(s.strength)}%`,
            }));
        },
        ...options
    });
};
