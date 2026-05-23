import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/auth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import YardList from './pages/YardList'
import StockInList from './pages/StockInList'
import StockOutList from './pages/StockOutList'
import StocktakeList from './pages/StocktakeList'
import TemperatureList from './pages/TemperatureList'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="yards" element={<YardList />} />
          <Route path="stock-in" element={<StockInList />} />
          <Route path="stock-out" element={<StockOutList />} />
          <Route path="stocktake" element={<StocktakeList />} />
          <Route path="temperature" element={<TemperatureList />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
