import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import type { SignalEvent } from '@/types';

interface SignalsListResponse {
    signals: Array<{
        id: number;
        ticker: string;
        signal_type: string;
        strength: number;
        confidence: number;
        timestamp: string;
        metadata: any;
    }>;
    total_count: number;
}

export const useSignals = (options = {}) => {
    return useQuery({
        queryKey: ['signals'],
        queryFn: async () => {
            const { data } = await apiClient.get<SignalsListResponse>('/signals');

            // Transform backend signals to frontend SignalEvent format
            return data.signals.map(s => ({
                time: new Date(s.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
                type: s.signal_type.toUpperCase() as SignalEvent['type'],
                text: `${s.ticker}: ${s.signal_type.replace(/_/g, ' ').toUpperCase()} Detected. Strength: ${s.strength}%`,
            }));
        },
        ...options
    });
};
