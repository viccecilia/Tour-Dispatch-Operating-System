import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/apiClient";

export function useApiStatus() {
  return useQuery({
    queryKey: ["api-status"],
    queryFn: api.ping,
    refetchInterval: 30_000,
  });
}
