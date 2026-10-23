import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';

interface ResearchReportResponse {
    ticker: string;
    summary: string;
    key_insights: string[];
    strengths: string[];
    weaknesses: string[];
    opportunities: string[];
    threats: string[];
    confidence_score: number;
    generated_at: string | null;
}

export const useResearch = (ticker: string, options = {}) => {
    return useQuery({
        queryKey: ['research', ticker],
        queryFn: async () => {
            if (!ticker) return null;
            const { data } = await apiClient.get<ResearchReportResponse>(`/stocks/${ticker}/research`);
            return data;
        },
        enabled: !!ticker,
        ...options
    });
};

/** Regenerate a report even if the cached one is fresh (rate-limited server-side). */
export const useRefreshResearch = (ticker: string) => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async () => {
            const { data } = await apiClient.get<ResearchReportResponse>(`/stocks/${ticker}/research`, {
                params: { refresh: true },
            });
            return data;
        },
        onSuccess: (data) => queryClient.setQueryData(['research', ticker], data),
    });
};
