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
