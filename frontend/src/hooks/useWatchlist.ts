import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

export interface WatchlistEntry {
    ticker: string;
    name: string;
    price: string;
    cap: string;
    risk: number;
    signal: string;
    alpha: string;
    status: string;
}

const KEY = ['watchlist'];

export const useWatchlist = () => {
    const { token } = useAuth();
    return useQuery({
        // Header widgets mount before sign-in completes; wait for a session
        enabled: !!token,
        queryKey: KEY,
        queryFn: async () => {
            const { data } = await apiClient.get<{ items: WatchlistEntry[] }>('/watchlist/');
            return data.items;
        },
    });
};

/** Add/remove a ticker; the server returns or implies the new list. */
export const useToggleWatch = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ ticker, watched }: { ticker: string; watched: boolean }) => {
            if (watched) {
                await apiClient.delete(`/watchlist/${encodeURIComponent(ticker)}`);
                return null;
            }
            const { data } = await apiClient.post<{ items: WatchlistEntry[] }>('/watchlist/', { ticker });
            return data.items;
        },
        onSuccess: (items, { ticker }) => {
            queryClient.setQueryData<WatchlistEntry[]>(KEY, (prev = []) =>
                items ?? prev.filter(i => i.ticker !== ticker)
            );
            // A newly verified ticker joins the stock universe
            queryClient.invalidateQueries({ queryKey: ['stocks', 'universe'] });
        },
    });
};
