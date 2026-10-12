import { useState, useRef, useEffect } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import axios from 'axios'
import './index.css'

const SplashScreen = () => {
  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, width: '100vw', height: '100vh',
      backgroundColor: 'var(--bg-main)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999
    }}>
      <div style={{
        position: 'relative',
        width: '350px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '2rem'
      }}>
        <div style={{
          position: 'absolute',
          top: '-45px',
          left: '0',
          fontSize: '3.5rem',
          animation: 'slideHand 2.5s cubic-bezier(0.4, 0, 0.2, 1) forwards',
          zIndex: 10
        }}>
          👇
        </div>
        
        <div style={{
          width: '100%',
          height: '45px',
          border: '4px solid var(--border-color)',
          backgroundColor: '#fff',
          boxShadow: '8px 8px 0px var(--border-color)',
          position: 'relative',
          overflow: 'hidden',
          borderRadius: '0px'
        }}>
          <div style={{
            height: '100%',
            backgroundColor: 'var(--btn-primary)',
            animation: 'fillBar 2.5s cubic-bezier(0.4, 0, 0.2, 1) forwards',
            borderRight: '4px solid var(--border-color)'
          }} />
        </div>
        
        <div style={{
          fontSize: '1.5rem',
          fontWeight: '900',
          textTransform: 'uppercase',
          letterSpacing: '2px',
          animation: 'pulseText 1s infinite alternate'
        }}>
          Initializing...
        </div>
      </div>

      <style>{`
        @keyframes slideHand {
          0% { left: 0%; transform: translateX(-50%) translateY(0); }
          50% { left: 50%; transform: translateX(-50%) translateY(-15px) rotate(-10deg); }
          100% { left: 100%; transform: translateX(-50%) translateY(0); }
        }
        @keyframes fillBar {
          0% { width: 0%; }
          100% { width: 100%; }
        }
        @keyframes pulseText {
          0% { opacity: 0.5; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
};

const ProductImage = ({ rec, style }) => {
  const rawUrls = rec?.score?.ext?.image_urls;
  const images = Array.isArray(rawUrls)
    ? rawUrls.filter(u => typeof u === 'string' && u.trim().startsWith('http'))
    : (typeof rawUrls === 'string' && rawUrls.trim().startsWith('http') ? [rawUrls.trim()] : []);

  const [currentIdx, setCurrentIdx] = useState(0);
  const [hasError, setHasError] = useState(false);

  const getFallbackIcon = () => {
    const cat = `${rec?.score?.ext?.cat_l1 || ''} ${rec?.score?.ext?.cat_l2 || ''} ${rec?.category || ''}`.toLowerCase();
    const name = (rec?.score?.ext?.name || rec?.product_id || '').toLowerCase();
    if (cat.includes('laptop') || name.includes('laptop') || name.includes('macbook') || name.includes('book') || name.includes('thinkpad')) return '💻';
    if (cat.includes('cell') || cat.includes('phone') || name.includes('phone') || name.includes('galaxy') || name.includes('iphone')) return '📱';
    if (cat.includes('tv') || name.includes('tv') || name.includes('television')) return '📺';
    if (cat.includes('headphone') || cat.includes('audio') || name.includes('headphone') || name.includes('earbuds')) return '🎧';
    return '📦';
  };

  if (!images.length || hasError || currentIdx >= images.length) {
    return (
      <span style={{ fontSize: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}>
        {getFallbackIcon()}
      </span>
    );
  }

  return (
    <img
      src={images[currentIdx]}
      alt={rec?.score?.ext?.name || 'Product'}
      referrerPolicy="no-referrer"
      crossOrigin="anonymous"
      loading="lazy"
      onError={() => {
        if (currentIdx + 1 < images.length) {
          setCurrentIdx(prev => prev + 1);
        } else {
          setHasError(true);
        }
      }}
      style={{
        width: '100%',
        height: '100%',
        objectFit: 'contain',
        backgroundColor: '#ffffff',
        borderRadius: '4px',
        ...style,
      }}
    />
  );
};

const ModalGallery = ({ product }) => {
  const rawUrls = product?.score?.ext?.image_urls;
  const images = Array.isArray(rawUrls)
    ? rawUrls.filter(u => typeof u === 'string' && u.trim().startsWith('http'))
    : (typeof rawUrls === 'string' && rawUrls.trim().startsWith('http') ? [rawUrls.trim()] : []);

  const [selectedIdx, setSelectedIdx] = useState(0);

  if (!images.length) {
    const cat = `${product?.score?.ext?.cat_l1 || ''} ${product?.score?.ext?.cat_l2 || ''} ${product?.category || ''}`.toLowerCase();
    const name = (product?.score?.ext?.name || '').toLowerCase();
    const icon = (cat.includes('laptop') || name.includes('laptop') || name.includes('macbook')) ? '💻' : (cat.includes('cell') || cat.includes('phone') || name.includes('phone')) ? '📱' : (cat.includes('tv') || name.includes('tv')) ? '📺' : '📦';
    return (
      <div style={{
        height: '160px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#f8fafc',
        border: '2px dashed var(--border-color)',
        borderRadius: '8px',
        fontSize: '3rem',
        marginBottom: '1rem'
      }}>
        {icon}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
      <div style={{
        width: '100%',
        height: '220px',
        backgroundColor: '#ffffff',
        border: '2px solid var(--border-color)',
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0.5rem',
        boxShadow: '3px 3px 0px var(--border-color)',
        overflow: 'hidden'
      }}>
        <img
          src={images[selectedIdx]}
          alt={product.score?.ext?.name || 'Product'}
          referrerPolicy="no-referrer"
          crossOrigin="anonymous"
          style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
        />
      </div>
      {images.length > 1 && (
        <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', maxWidth: '100%', padding: '0.25rem' }}>
          {images.map((img, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedIdx(idx)}
              style={{
                width: '46px',
                height: '46px',
                padding: '2px',
                backgroundColor: '#ffffff',
                border: idx === selectedIdx ? '2px solid #2563eb' : '1px solid var(--border-color)',
                borderRadius: '4px',
                cursor: 'pointer',
                opacity: idx === selectedIdx ? 1 : 0.6,
                transform: idx === selectedIdx ? 'scale(1.05)' : 'none',
                transition: 'all 0.15s ease',
                flexShrink: 0
              }}
            >
              <img
                src={img}
                alt="thumb"
                referrerPolicy="no-referrer"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

function App() {
  const { loginWithRedirect, logout, isAuthenticated, user, getAccessTokenSilently, isLoading } = useAuth0();
  
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setMinTimeElapsed(true), 2500);
    return () => clearTimeout(timer);
  }, []);
  
  // Persist session and messages in localStorage
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem('chatSessionId') || crypto.randomUUID();
  });
  const activeSessionRef = useRef(sessionId);
  
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem('chatMessages');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem('chatSessionId', sessionId);
    activeSessionRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    localStorage.setItem('chatMessages', JSON.stringify(messages));
  }, [messages]);

  const [input, setInput] = useState('');
  const [loadingSessions, setLoadingSessions] = useState(new Set());
  const loading = loadingSessions.has(sessionId);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    return localStorage.getItem('theme') === 'dark';
  });
  
  const [chatSessions, setChatSessions] = useState(() => {
    try {
      const saved = localStorage.getItem('chatSessions');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem('chatSessions', JSON.stringify(chatSessions));
  }, [chatSessions]);

  useEffect(() => {
    if (messages.length > 0) {
      setChatSessions(prev => {
        const existingIndex = prev.findIndex(s => s.id === sessionId);
        const title = messages[0]?.content || 'New Chat';
        const updated = [...prev];
        if (existingIndex >= 0) {
          updated[existingIndex] = { ...updated[existingIndex], messages, title };
        } else {
          updated.unshift({ id: sessionId, title, messages, timestamp: Date.now() });
        }
        return updated;
      });
    }
  }, [messages, sessionId]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (isDarkTheme) {
      document.body.classList.add('dark-theme');
      localStorage.setItem('theme', 'dark');
    } else {
      document.body.classList.remove('dark-theme');
      localStorage.setItem('theme', 'light');
    }
  }, [isDarkTheme]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userQuery = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userQuery }]);
    setLoadingSessions(prev => new Set([...prev, sessionId]));

    try {
      let token = 'dummy_token_if_auth_disabled';
      if (isAuthenticated) {
        token = await getAccessTokenSilently();
      }

      // Format previous messages for chat_history
      const chat_history = messages.map(msg => {
        if (msg.role === 'user') return { role: 'user', content: msg.content };
        if (msg.error) return { role: 'assistant', content: `Error: ${msg.error}` };
        const d = msg.data;
        if (!d) return { role: 'assistant', content: 'Unknown error' };
        if (d.status === 'abstained') return { role: 'assistant', content: d.message || "Couldn't find a matching product." };
        if (d.status === 'needs_clarification') return { role: 'assistant', content: d.message };
        if (d.recommendations && d.recommendations.length > 0) {
          const recs = d.recommendations.map(r => `- ${r.score.ext?.name || "Product"}`).join('\n');
          return { role: 'assistant', content: `Recommendations:\n${recs}` };
        }
        return { role: 'assistant', content: d.message || "Unknown response" };
      });

      const res = await axios.post('http://localhost:8000/api/advise', {
        query: userQuery,
        session_id: sessionId,
        chat_history: chat_history
      }, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      const data = res.data.response;
      if (activeSessionRef.current === sessionId) {
        setMessages(prev => [...prev, { role: 'assistant', data }]);
      } else {
        // User switched chats mid-flight. Save it to the original session in the background.
        setChatSessions(prev => {
          const updated = [...prev];
          const idx = updated.findIndex(s => s.id === sessionId);
          if (idx >= 0) {
            updated[idx] = { ...updated[idx], messages: [...updated[idx].messages, { role: 'assistant', data }] };
          }
          return updated;
        });
      }
    } catch (err) {
      console.error(err);
      if (activeSessionRef.current === sessionId) {
        setMessages(prev => [...prev, { role: 'assistant', error: 'Network or server error occurred.' }]);
      }
    } finally {
      setLoadingSessions(prev => {
        const n = new Set(prev);
        n.delete(sessionId);
        return n;
      });
    }
  }

  const handleCopyChat = () => {
    if (messages.length === 0) {
      alert("Chat is empty!");
      return;
    }
    const textToCopy = messages.map(msg => {
      if (msg.role === 'user') {
        return `You: ${msg.content}`;
      } else {
        if (msg.error) return `AI: Error - ${msg.error}`;
        const d = msg.data;
        if (d.status === 'abstained') return `AI: Abstained - ${d.message || "Couldn't find a matching product."}`;
        if (d.status === 'needs_clarification') return `AI: Clarification Needed - ${d.message}`;
        if (d.recommendations && d.recommendations.length > 0) {
          const recs = d.recommendations.map(r => `- ${r.score.ext?.name || "Product"} (Score: ${r.score.total.toFixed(2)})`).join('\n');
          return `AI: Recommendations:\n${recs}`;
        }
        return `AI: ${d.message || "Unknown response"}`;
      }
    }).join('\n\n');

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        alert("Chat copied to clipboard!");
      }).catch(err => {
        console.error("Failed to copy: ", err);
        fallbackCopyTextToClipboard(textToCopy);
      });
    } else {
      fallbackCopyTextToClipboard(textToCopy);
    }
  };

  const fallbackCopyTextToClipboard = (text) => {
    var textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      var successful = document.execCommand('copy');
      if (successful) alert("Chat copied to clipboard!");
      else alert("Copying failed. Please copy manually.");
    } catch (err) {
      console.error('Fallback: Oops, unable to copy', err);
      alert("Copying failed. Please copy manually.");
    }
    document.body.removeChild(textArea);
  };

  const handleNewChat = () => {
    setMessages([]);
    setSessionId(crypto.randomUUID());
    setSelectedProduct(null);
  };

  // Neo-brutalism window controls
  const WindowControls = () => (
    <div className="window-dots">
      <div className="dot red"></div>
      <div className="dot yellow"></div>
      <div className="dot green"></div>
    </div>
  );

  const showSplash = isLoading || !minTimeElapsed;
  if (showSplash) {
    return <SplashScreen />;
  }

  return (
    <>
      <div className="neo-window app-container">
        {/* Main Header */}
        <header className="neo-header purple">
          <WindowControls />
          <span style={{marginRight: 'auto', fontSize: '1.1rem'}}>AI Product Advisor</span>
          
          <div style={{display: 'flex', gap: '1rem', alignItems: 'center'}}>
            <button className="neo-btn" style={{padding: '0.25rem 0.75rem', backgroundColor: 'var(--btn-secondary)'}} onClick={() => setIsDarkTheme(t => !t)}>
              {isDarkTheme ? '☀️ Light' : '🌙 Dark'}
            </button>
            {isAuthenticated ? (
              <>
                <span className="neo-pill pill-yellow" style={{margin:0, border:'2px solid var(--border-color)', color: 'black'}}>{user?.name || "User"}</span>
                <button className="neo-btn" style={{padding: '0.25rem 0.75rem', backgroundColor: 'var(--btn-secondary)'}} onClick={() => {
                  logout({ logoutParams: { returnTo: window.location.origin } });
                }}>Logout</button>
              </>
            ) : (
              <button className="neo-btn" style={{padding: '0.25rem 0.75rem'}} onClick={() => loginWithRedirect()}>Login</button>
            )}
          </div>
        </header>

        <div className="app-body">
          {/* Sidebar */}
          {isAuthenticated && (
            <aside className="sidebar">
              <div className="sidebar-title">
                <span style={{fontSize: '2rem'}}>👾</span> ADVISOR
              </div>
              
              <div style={{marginTop: '1.5rem', display: 'flex', flexDirection: 'column', flex: 1}}>
                <div style={{fontSize: '0.9rem', fontWeight: '800', marginBottom: '1rem', textTransform: 'uppercase'}}>Previous Chats</div>
                    {chatSessions.length === 0 ? (
                      <div style={{fontSize: '0.8rem', color: '#64748b'}}>No history yet.</div>
                    ) : (
                      <div style={{display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '30vh', overflowY: 'auto', paddingRight: '0.2rem'}}>
                        {chatSessions.map(session => (
                          <div 
                            key={session.id} 
                            className="menu-item" 
                            style={{ 
                              fontSize: '0.85rem', 
                              padding: '0.5rem', 
                              whiteSpace: 'nowrap', 
                              overflow: 'hidden', 
                              textOverflow: 'ellipsis',
                              backgroundColor: session.id === sessionId ? 'var(--window-header-main)' : '',
                              color: session.id === sessionId ? '#000' : ''
                            }}
                            onClick={() => {
                              setSessionId(session.id);
                              setMessages(session.messages);
                            }}
                          >
                            💬 {session.title}
                            {loadingSessions.has(session.id) && (
                              <span style={{marginLeft: '0.5rem', display: 'inline-block', animation: 'spin 2s linear infinite'}}>🔄</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
              </div>
              
              <div style={{marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem'}}>
                 {isAuthenticated && (
                   <>
                     <button className="neo-btn" style={{backgroundColor: 'var(--btn-secondary)', width: '100%', padding: '0.5rem'}} onClick={handleNewChat}>
                       ✨ New Chat
                     </button>
                     <button className="neo-btn" style={{backgroundColor: 'var(--btn-accent)', width: '100%', padding: '0.5rem'}} onClick={handleCopyChat}>
                       📋 Copy Chat
                     </button>
                   </>
                 )}
                 <p style={{fontSize: '0.8rem', fontWeight: '600'}}>Powered by Agentic AI</p>
              </div>
            </aside>
          )}

          {/* Main Content */}
          <main className="main-content">
            
            {!isAuthenticated ? (
              <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%'}}>
                <div style={{
                  backgroundColor: 'var(--bg-main)', 
                  border: '4px solid var(--border-color)', 
                  boxShadow: '8px 8px 0px var(--border-color)', 
                  padding: '3rem',
                  maxWidth: '450px',
                  width: '100%',
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.5rem',
                  borderRadius: '0px'
                }}>
                  <div style={{fontSize: '4rem', margin: '0 auto', lineHeight: 1}}>👾</div>
                  <h2 style={{fontSize: '2.2rem', fontWeight: '800', margin: 0, lineHeight: 1.2}}>Welcome back!</h2>
                  <p style={{fontSize: '1.1rem', margin: 0, fontWeight: '500'}}>Log in or sign up to discover the perfect product recommended by our Agentic AI.</p>
                  
                  <div style={{display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem'}}>
                    <button 
                      className="neo-btn" 
                      style={{backgroundColor: 'var(--btn-primary)', padding: '1rem', fontSize: '1.2rem'}}
                      onClick={() => loginWithRedirect({ authorizationParams: { prompt: 'login' } })}
                    >
                      Login to Account
                    </button>
                    <button 
                      className="neo-btn" 
                      style={{backgroundColor: 'var(--window-header-main)', padding: '1rem', fontSize: '1.2rem'}}
                      onClick={() => loginWithRedirect({ authorizationParams: { prompt: 'login', screen_hint: 'signup' } })}
                    >
                      Create New Account
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="messages-container">
                  <h2 style={{fontSize: '1.5rem', textAlign: 'center', marginBottom: '1rem'}}>The product stars aligned and chose...</h2>
                  
                  {messages.length === 0 && (
                    <div style={{textAlign: 'center', color: '#64748b'}}>
                      Your recommendations will appear here.
                    </div>
                  )}

                  {messages.map((msg, i) => {
                    if (msg.role === 'user') {
                      return (
                        <div key={i} className="message-box user">
                          <span className="neo-pill pill-pink">You asked</span>
                          <h3 style={{fontSize: '1.25rem', marginTop: '0.5rem'}}>{msg.content}</h3>
                        </div>
                      );
                    } else {
                      // Assistant message rendering
                      if (msg.error) {
                         return <div key={i} className="message-box assistant"><span className="neo-pill pill-red">Error</span><p>{msg.error}</p></div>
                      }
                      
                      const data = msg.data;
                      if (data.status === 'abstained') {
                        return (
                          <div key={i} className="message-box assistant">
                            <span className="neo-pill pill-yellow">Abstained</span>
                            <p style={{fontSize: '1.1rem', fontWeight: '600', marginTop: '0.5rem'}}>🚫 {data.message || "I couldn't find a matching product."}</p>
                          </div>
                        )
                      }
                      
                      if (data.status === 'needs_clarification') {
                        return (
                          <div key={i} className="message-box assistant">
                            <span className="neo-pill pill-teal">Clarification needed</span>
                            <p style={{fontSize: '1.1rem', fontWeight: '600', marginTop: '0.5rem'}}>🤔 {data.message}</p>
                            {data.suggested_answers && data.suggested_answers.length > 0 && (
                              <div style={{marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem'}}>
                                {data.suggested_answers.map((ans, aIdx) => (
                                  <button
                                    key={aIdx}
                                    className="neo-btn"
                                    style={{
                                      padding: '0.4rem 1rem',
                                      backgroundColor: 'var(--accent-teal)',
                                      border: '2px solid var(--border-color)',
                                      boxShadow: '3px 3px 0px var(--shadow-color)',
                                      cursor: 'pointer',
                                      fontWeight: '700',
                                      fontSize: '0.9rem',
                                      transition: 'transform 0.1s, box-shadow 0.1s',
                                    }}
                                    onMouseEnter={e => { e.target.style.transform='translate(-2px,-2px)'; e.target.style.boxShadow='5px 5px 0px var(--shadow-color)'; }}
                                    onMouseLeave={e => { e.target.style.transform=''; e.target.style.boxShadow='3px 3px 0px var(--shadow-color)'; }}
                                    onClick={() => {
                                      setInput(ans);
                                      // auto-send by simulating the form submit
                                      setTimeout(() => document.getElementById('chat-send-btn').click(), 50);
                                    }}
                                  >
                                    {ans}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      }

                      if (data.recommendations && data.recommendations.length > 0) {
                        return (
                          <div key={i} className="message-box assistant" style={{width: '100%', maxWidth: '100%'}}>
                            <span className="neo-pill pill-teal">Recommendations</span>
                            
                            {data.degraded?.map((d, idx) =>(
                               null // WHY: degradation signals are internal — hide from users
                            ))}

                            <div style={{display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem'}}>
                              {data.recommendations.map((rec, rIdx) => (
                                <div key={rIdx} className="product-card" style={{alignItems: 'flex-start'}}>
                                  <div className="product-image" style={{overflow: 'hidden', backgroundColor: '#ffffff'}}>
                                    <ProductImage rec={rec} />
                                  </div>
                                  <div className="product-info" style={{flex: 1}}>
                                    <h3>{rec.score.ext?.name || rec.product_id}</h3>
                                    <div style={{display: 'flex', gap: '0.5rem', margin: '0.5rem 0'}}>
                                      <span className="neo-pill pill-yellow" style={{margin: 0, padding: '0.1rem 0.5rem', fontSize: '0.75rem'}}>
                                        Score: {rec.score?.total.toFixed(2)}
                                      </span>
                                    </div>
                                    <p style={{marginTop: '0.5rem', fontSize: '0.95rem', lineHeight: '1.4'}}>{rec.paragraph}</p>
                                  </div>
                                  <div style={{display: 'flex', flexDirection: 'column', gap: '0.5rem', marginLeft: '1rem', alignSelf: 'center'}}>
                                    <button 
                                      className="neo-btn" 
                                      style={{padding: '0.5rem 1rem', fontSize: '0.875rem', backgroundColor: '#fca5a5'}}
                                      onClick={() => setSelectedProduct(rec)}
                                    >
                                      View Specs
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )
                      }
                      
                      return <div key={i} className="message-box assistant"><p>No results found.</p></div>
                    }
                  })}
                  
                  {loading && (
                    <div className="message-box assistant">
                      <span className="neo-pill pill-teal">Thinking...</span>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Window (Mood Picker style) */}
                <div className="neo-window input-window">
                  <header className="neo-header teal">
                    <WindowControls />
                    <span>Product Picker</span>
                  </header>
                  <form className="neo-input-group" onSubmit={handleSend}>
                    <input 
                      type="text" 
                      className="neo-input"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="What are you looking for today?"
                      disabled={loading}
                    />
                    <button id="chat-send-btn" className="neo-btn" type="submit" disabled={loading || !input.trim()}>
                      ➤
                    </button>
                  </form>
                </div>
              </>
            )}
          </main>
        </div>
      </div>

      {/* Specs Modal */}
      {selectedProduct && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
          backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }} onClick={() => setSelectedProduct(null)}>
          <div className="neo-window" style={{
            width: '90%', maxWidth: '620px', backgroundColor: '#fff',
            maxHeight: '85vh', overflowY: 'auto'
          }} onClick={e => e.stopPropagation()}>
            <header className="neo-header pink">
              <WindowControls />
              <span style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                Specs: {selectedProduct.score.ext?.name || selectedProduct.product_id}
              </span>
              <button className="neo-btn" style={{padding: '0.2rem 0.5rem', backgroundColor: '#e2e8f0'}} onClick={() => setSelectedProduct(null)}>X</button>
            </header>
            <div style={{padding: '1.5rem'}}>
              {/* Product Gallery in Modal */}
              <ModalGallery product={selectedProduct} />

              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem'}}>
                {selectedProduct.score.ext?.effective_price_inr && (
                  <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: '#059669'}}>
                    ₹{selectedProduct.score.ext.effective_price_inr.toLocaleString()}
                  </div>
                )}
                {selectedProduct.score.ext?.brand && (
                  <span className="neo-pill pill-yellow" style={{margin: 0, fontWeight: 'bold'}}>
                    Brand: {selectedProduct.score.ext.brand}
                  </span>
                )}
              </div>

              {selectedProduct.score.ext?.url && (
                <div style={{marginBottom: '1.25rem'}}>
                  <a 
                    href={selectedProduct.score.ext.url} 
                    target="_blank" 
                    rel="noreferrer"
                    className="neo-btn"
                    style={{display: 'inline-block', textDecoration: 'none', backgroundColor: '#38bdf8', color: 'black', fontWeight: 'bold'}}
                  >
                    🛒 View on Amazon
                  </a>
                </div>
              )}
              <div>
                <h4 style={{fontSize: '1.1rem', marginBottom: '0.5rem'}}>Description / Specifications:</h4>
                <p style={{lineHeight: '1.6', color: '#334155', whiteSpace: 'pre-wrap', fontSize: '0.95rem'}}>
                  {selectedProduct.score.ext?.description || "No detailed specs available."}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default App
