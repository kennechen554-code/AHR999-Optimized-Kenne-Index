import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '../services/api'

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
  })
}

