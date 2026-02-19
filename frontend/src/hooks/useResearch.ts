import { useQuery } from '@tanstack/react-query';
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
