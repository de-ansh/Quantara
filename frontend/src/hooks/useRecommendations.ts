import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';

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
        reasoning_metadata: Record<string, unknown>;
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
                risk: Number(r.reasoning_metadata.risk_score),
                research: Math.round(r.scores.research_score),
                signal: r.scores.signal_score > 70 ? 'up' : 'right' as "up" | "up-right" | "right" | "down",
                score: r.scores.final_score.toFixed(1),
                alignment: `${r.scores.risk_alignment_score.toFixed(1)}%`,
            }));
        },
        ...options
    });
};
