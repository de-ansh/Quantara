import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import type { SignalEvent } from '@/types';
import type { ApiSignal } from '@/types/api';

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
                type: s.signal_type.toUpperCase() as SignalEvent['type'],
                text: `${s.ticker}: ${s.signal_type.replace(/_/g, ' ').toUpperCase()} Detected. Strength: ${Math.round(s.strength)}%`,
            }));
        },
        ...options
    });
};
