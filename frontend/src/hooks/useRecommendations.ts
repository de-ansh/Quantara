import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import type { Opportunity } from '@/types';

interface RecommendationResponse {
    recommendations: Array<{
        ticker: string;
        rank: number;
        scores: {
            research_score: number;
            signal_score: number;
            risk_alignment_score: number;
            macro_fit_score: number;
            final_score: number;
        };
        explanation: string;
        reasoning_metadata: any;
    }>;
    total_count: number;
    user_risk_level: string;
}

export const useRecommendations = (options = {}) => {
    return useQuery({
        queryKey: ['recommendations'],
        queryFn: async () => {
            const { data } = await apiClient.get<RecommendationResponse>('/recommendations');

            // Transform backend recommendations to frontend Opportunity format
            return data.recommendations.map(r => ({
                ticker: r.ticker,
                name: r.ticker, // Backend doesn't provide name yet
                risk: (100 - r.scores.risk_alignment_score).toFixed(1),
                research: Math.round(r.scores.research_score),
                signal: r.scores.signal_score > 70 ? 'up' : 'right' as "up" | "up-right" | "right" | "down",
                return: `+${(r.scores.final_score / 10).toFixed(2)}%`,
                alignment: `${r.scores.risk_alignment_score.toFixed(1)}%`,
            }));
        },
        ...options
    });
};
