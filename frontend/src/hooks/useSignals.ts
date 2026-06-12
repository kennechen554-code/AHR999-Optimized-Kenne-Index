import { useQuery } from '@tanstack/react-query'
import { fetchSignals } from '../services/api'

export function useSignals() {
  return useQuery({
    queryKey: ['signals'],
    queryFn: fetchSignals,
  })
}
