import { useContext, createContext } from 'react';
import { DataContextValue } from './types';

export const DataContext = createContext<DataContextValue | undefined>(undefined);

export function useData(): DataContextValue {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData must be used within a DataProvider');
  }
  return context;
}
