import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

const SUGGESTIONS = [
  "I need a low voltage circuit breaker for a high current rating",
  "Show me thermal overload relays with a 15-25A range",
  "Looking for a 3-pole contactor for motor control",
  "What is the breaking capacity of the MasterPact MTZ2?"
];

function App() {
  const [messages, setMessages] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState({
    provider: 'gemini',
    chat_model: '',
    embedding_model: '',
    db_indexed: false,
    num_chunks: 0,
    indexing_in_progress: false,
    database_path: ''
  });

  const chatEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Fetch DB & model configuration status
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        
        // Start polling if indexing is in progress
        if (data.indexing_in_progress) {
          startPolling();
        } else if (!data.indexing_in_progress && pollIntervalRef.current) {
          stopPolling();
        }
      }
    } catch (err) {
      console.error("Failed to fetch status:", err);
    }
  };

  const startPolling = () => {
    if (pollIntervalRef.current) return;
    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          if (!data.indexing_in_progress) {
            stopPolling();
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 3000);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  useEffect(() => {
    fetchStatus();
    return () => stopPolling();
  }, []);

  // Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Trigger indexing on PDFs
  const handleIndexPDFs = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/index`, { method: 'POST' });
      if (res.ok) {
        fetchStatus();
      }
    } catch (err) {
      console.error("Failed to start indexing:", err);
      alert("Error starting indexing process.");
    }
  };

  // Send a message to backend
  const handleSendMessage = async (textToSend) => {
    const text = textToSend || input;
    if (!text.trim()) return;

    if (!textToSend) setInput('');

    // Append user message
    const updatedMessages = [...messages, { role: 'user', content: text }];
    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: updatedMessages.map(m => ({
            role: m.role,
            content: m.content
          }))
        })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, { role: 'assistant', content: data.chat_response }]);
        if (data.recommendations && data.recommendations.length > 0) {
          setRecommendations(data.recommendations);
        }
      } else {
        const errorData = await res.json();
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: `Sorry, I ran into an error processing your request: ${errorData.detail || 'Server error'}` 
        }]);
      }
    } catch (err) {
      console.error("Chat error:", err);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "I'm having trouble connecting to the backend. Please make sure the FastAPI server is running." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const resetChat = () => {
    setMessages([]);
    setRecommendations([]);
  };

  // Simple Markdown text formatter for Chat Bubbles
  const formatText = (text) => {
    if (!text) return '';
    return text.split('\n').map((line, idx) => {
      // Bold formatter
      let formattedLine = line;
      const boldRegex = /\*\*(.*?)\*\*/g;
      formattedLine = formattedLine.replace(boldRegex, '<strong>$1</strong>');

      // Code formatter
      const codeRegex = /`(.*?)`/g;
      formattedLine = formattedLine.replace(codeRegex, '<code>$1</code>');

      // Check for bullet list item
      if (line.trim().startsWith('- ')) {
        const content = formattedLine.replace(/^\s*-\s+/, '');
        return <li key={idx} dangerouslySetInnerHTML={{ __html: content }} />;
      }
      if (line.trim().startsWith('* ')) {
        const content = formattedLine.replace(/^\s*\*\s+/, '');
        return <li key={idx} dangerouslySetInnerHTML={{ __html: content }} />;
      }

      return <p key={idx} dangerouslySetInnerHTML={{ __html: formattedLine }} />;
    });
  };

  return (
    <>
      {/* App Header */}
      <header className="app-header">
        <div className="logo-section">
          <div className="logo-icon">⚡</div>
          <div className="logo-text">
            <h1>Discovery Spark</h1>
            <p>Electrical RAG Discovery Agent</p>
          </div>
        </div>

        <div className="status-bar">
          <div className="status-badge">
            <span className={`status-dot ${status.db_indexed ? 'active' : ''} ${status.indexing_in_progress ? 'loading' : ''}`}></span>
            <span>
              {status.indexing_in_progress 
                ? 'Indexing Catalogs...' 
                : status.db_indexed 
                  ? `Database: Ready (${status.num_chunks} chunks)` 
                  : 'Database: Not Indexed'}
            </span>
          </div>

          <div className="status-badge">
            <span className="status-dot active"></span>
            <span style={{ textTransform: 'capitalize' }}>
              {status.provider}: {status.chat_model || 'Connecting...'}
            </span>
          </div>

          <button 
            className="btn btn-secondary" 
            onClick={handleIndexPDFs} 
            disabled={status.indexing_in_progress}
          >
            {status.indexing_in_progress ? 'Processing...' : 'Re-index PDFs'}
          </button>
          
          <button className="btn btn-secondary" onClick={resetChat}>
            Reset Chat
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="app-container">
        
        {/* Indexing Overlay if database is empty and not indexing */}
        {!status.db_indexed && !status.indexing_in_progress && (
          <div className="indexing-panel">
            <div className="indexing-card">
              <div className="indexing-logo">⚡</div>
              <h2>PDF Catalogs Not Indexed Yet</h2>
              <p>
                We found your product manuals in the <code>PDFs/</code> folder, but they haven't been indexed into the vector database.
                Click below to parse the files, generate cloud embeddings, and set up your catalog.
              </p>
              <button className="btn btn-large" onClick={handleIndexPDFs} style={{ padding: '12px 24px', fontSize: '15px' }}>
                🚀 Start Indexing Product Manuals
              </button>
            </div>
          </div>
        )}

        {/* Indexing Overlay if indexing is in progress */}
        {status.indexing_in_progress && messages.length === 0 && (
          <div className="indexing-panel">
            <div className="indexing-card">
              <div className="loader loader-large"></div>
              <h2>Indexing Electrical Component Manuals</h2>
              <p>
                We are currently extracting text, dividing it into overlapping chunks, generating vector embeddings via {status.provider === 'openai' ? 'OpenAI' : 'Gemini'} and loading them into LanceDB.
                This will take a minute. Please wait...
              </p>
              <div className="status-badge" style={{ marginTop: '10px' }}>
                <span>Processed chunks so far: {status.num_chunks}</span>
              </div>
            </div>
          </div>
        )}

        {/* Left Panel: Chat Interface */}
        <section className="chat-panel">
          <div className="chat-history">
            {messages.length === 0 ? (
              <div style={{ margin: 'auto', textAlign: 'center', maxWidth: '450px', padding: '20px' }}>
                <h2 style={{ fontSize: '24px', marginBottom: '12px', fontWeight: '500' }}>Welcome to Discovery Spark</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '15px', lineHeight: '1.6' }}>
                  I am your Electrical Component Discovery Agent. I can search through the electrical product brochures and catalogs in your <code>PDFs</code> directory to find the right part numbers, specifications, and configurations.
                </p>
                <p style={{ color: 'var(--color-primary)', marginTop: '20px', fontSize: '14px' }}>
                  Ask me about circuit breakers, overload relays, contactors, or other equipment.
                </p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`message-bubble ${msg.role === 'user' ? 'user' : 'assistant'}`}>
                  <div className="avatar">
                    {msg.role === 'user' ? 'U' : 'AI'}
                  </div>
                  <div className="message-content">
                    {msg.role === 'user' ? <p>{msg.content}</p> : formatText(msg.content)}
                  </div>
                </div>
              ))
            )}
            
            {isLoading && (
              <div className="message-bubble assistant">
                <div className="avatar">AI</div>
                <div className="message-content" style={{ display: 'flex', alignItems: 'center' }}>
                  <div className="typing-indicator">
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Suggestions */}
          {messages.length === 0 && (
            <div className="suggestions-container">
              {SUGGESTIONS.map((s, idx) => (
                <button 
                  key={idx} 
                  className="suggestion-chip" 
                  onClick={() => handleSendMessage(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Chat Input */}
          <div className="chat-input-container">
            <div className="chat-input-wrapper">
              <textarea
                className="chat-input"
                rows="1"
                placeholder={status.db_indexed ? "Ask about current rating, voltage, part numbers..." : "Waiting for indexing..."}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading || !status.db_indexed}
              />
              <button 
                className="send-btn" 
                onClick={() => handleSendMessage()}
                disabled={isLoading || !input.trim() || !status.db_indexed}
              >
                ➔
              </button>
            </div>
          </div>
        </section>

        {/* Right Panel: Recommendations */}
        <section className="rec-panel">
          <div className="rec-header">
            <h2>Recommended Products</h2>
            <div className="rec-count">
              {recommendations.length} {recommendations.length === 1 ? 'Product' : 'Products'}
            </div>
          </div>

          <div className="rec-list">
            {recommendations.length === 0 ? (
              <div className="rec-placeholder">
                <div className="rec-placeholder-icon">⚡</div>
                <h3>No Recommendations Yet</h3>
                <p style={{ maxWidth: '280px', fontSize: '13.5px', marginTop: '8px' }}>
                  Chat with the agent, share your parameters, and the top 3 matching items will appear here in real-time.
                </p>
              </div>
            ) : (
              recommendations.map((prod, idx) => (
                <div key={idx} className="product-card">
                  <div className="product-card-header">
                    <h3 className="product-title">{prod.name}</h3>
                    <span className="product-rank">Top {idx + 1}</span>
                  </div>
                  
                  {prod.part_number && (
                    <div className="product-part-number">
                      {prod.part_number}
                    </div>
                  )}

                  {prod.specs && (
                    <div className="product-specs">
                      {prod.specs}
                    </div>
                  )}

                  {prod.match_reason && (
                    <div className="product-reason">
                      <strong>Match Reason:</strong> {prod.match_reason}
                    </div>
                  )}

                  {prod.pdf_source && (
                    <div className="product-citation">
                      <span className="product-citation-icon">📄</span>
                      <span>Source: {prod.pdf_source}</span>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

      </div>
    </>
  );
}

export default App;
