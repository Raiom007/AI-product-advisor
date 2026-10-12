import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { Auth0Provider } from '@auth0/auth0-react'

// Replace these with actual Auth0 credentials later
const domain = import.meta.env.VITE_AUTH0_DOMAIN || "dev-placeholder.auth0.com";
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID || "placeholder_client_id";

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: window.location.origin
      }}
    >
      <App />
    </Auth0Provider>
  </React.StrictMode>,
)
