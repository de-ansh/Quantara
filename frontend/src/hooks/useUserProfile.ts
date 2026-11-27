import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';

export interface UserProfile {
    id: number;
    email: string;
    risk_level: string | null;
    volatility_tolerance: number | null;
    investment_horizon: number | null; // months
    sector_preferences: Record<string, number> | null; // sector -> 1 for a preferred one
}

/** The signed-in user's risk profile; Account invalidates it on save. */
export const useUserProfile = () => useQuery({
    queryKey: ['userProfile'],
    queryFn: async () => (await apiClient.get<UserProfile>('/users/me')).data,
});

/** Sectors the user marked as preferred on Account. */
export const usePreferredSectors = (): Set<string> => {
    const { data } = useUserProfile();
    return new Set(Object.entries(data?.sector_preferences ?? {}).filter(([, v]) => v > 0).map(([k]) => k));
};
