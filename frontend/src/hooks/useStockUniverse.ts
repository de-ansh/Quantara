import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import { useWatchlist } from '@/hooks/useWatchlist';

/**
 * Tickers tracked in the stocks table, for quick-pick chips and selectors.
 */
export const useStockUniverse = () => {
    return useQuery({
        queryKey: ['stocks', 'universe'],
        queryFn: async () => {
            const { data } = await apiClient.get<{ stocks: Array<{ ticker: string }> }>('/stocks/search', {
                params: { limit: 200 },
            });
            return data.stocks.map(s => s.ticker);
        },
        staleTime: 5 * 60 * 1000,
    });
};

/** Quick-pick tickers: the user's watchlist first, then the rest of the universe. */
export const useQuickTickers = (): string[] => {
    const { data: universe = [] } = useStockUniverse();
    const { data: watchlist = [] } = useWatchlist();
    const watched = watchlist.map(w => w.ticker);
    return [...watched, ...universe.filter(t => !watched.includes(t))];
};
