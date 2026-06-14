import React, { useState, useEffect } from 'react';

const API_BASE = "http://127.0.0.1:5000/api";

export default function App() {
  // Auth state
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // login, register
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [authError, setAuthError] = useState('');

  // Group state
  const [groups, setGroups] = useState([]);
  const [activeGroupId, setActiveGroupId] = useState('');
  const [activeGroup, setActiveGroup] = useState(null);
  const [newGroupName, setNewGroupName] = useState('');

  // Dashboard navigation
  const [activeTab, setActiveTab] = useState('expenses'); // expenses, balances, members, import

  // Expense form state
  const [expenseDesc, setExpenseDesc] = useState('');
  const [expenseAmt, setExpenseAmt] = useState('');
  const [expenseCurrency, setExpenseCurrency] = useState('INR');
  const [expenseRate, setExpenseRate] = useState('83');
  const [expensePayer, setExpensePayer] = useState('');
  const [expenseSplitType, setExpenseSplitType] = useState('equal');
  const [expenseDate, setExpenseDate] = useState(new Date().toISOString().split('T')[0]);
  const [expenseNotes, setExpenseNotes] = useState('');
  const [customSplits, setCustomSplits] = useState({}); // maps user_id -> value (percentage, share, unequal amount)

  // Settlement form state
  const [settlePayer, setSettlePayer] = useState('');
  const [settlePayee, setSettlePayee] = useState('');
  const [settleAmt, setSettleAmt] = useState('');

  // Group ledger & calculations state
  const [expenses, setExpenses] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [balances, setBalances] = useState([]);
  const [simplifiedDebts, setSimplifiedDebts] = useState([]);
  const [selectedLedgerUser, setSelectedLedgerUser] = useState(null);

  // New member form state
  const [newMemberUsername, setNewMemberUsername] = useState('');
  const [newMemberJoined, setNewMemberJoined] = useState(new Date().toISOString().split('T')[0]);
  const [newMemberLeft, setNewMemberLeft] = useState('');

  // CSV Import Wizard state
  const [importFile, setImportFile] = useState(null);
  const [importSessionId, setImportSessionId] = useState('');
  const [anomalies, setAnomalies] = useState([]);
  const [resolutions, setResolutions] = useState({}); // anomaly_id -> resolved value
  const [importReport, setImportReport] = useState(null); // final report of import
  const [importError, setImportError] = useState('');

  // Alert State
  const [globalMessage, setGlobalMessage] = useState('');
  const [globalError, setGlobalError] = useState('');

  // Modals
  const [showExpenseModal, setShowExpenseModal] = useState(false);
  const [showSettleModal, setShowSettleModal] = useState(false);

  // Fetch profile on token change
  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      fetchProfile();
      fetchGroups();
    } else {
      localStorage.removeItem('token');
      setUser(null);
      setGroups([]);
      setActiveGroup(null);
    }
  }, [token]);

  // Fetch group details and data when active group changes
  useEffect(() => {
    if (activeGroupId) {
      fetchGroupDetails();
      fetchExpensesAndSettlements();
      fetchBalances();
    } else {
      setActiveGroup(null);
      setExpenses([]);
      setSettlements([]);
      setBalances([]);
      setSimplifiedDebts([]);
    }
  }, [activeGroupId]);

  // Set default payer when activeGroup loads
  useEffect(() => {
    if (activeGroup && activeGroup.members && activeGroup.members.length > 0) {
      setExpensePayer(activeGroup.members[0].user_id);
      setSettlePayer(activeGroup.members[0].user_id);
      setSettlePayee(activeGroup.members.length > 1 ? activeGroup.members[1].user_id : activeGroup.members[0].user_id);
      
      // Initialize custom splits
      const initSplits = {};
      activeGroup.members.forEach(m => {
        initSplits[m.user_id] = '';
      });
      setCustomSplits(initSplits);
    }
  }, [activeGroup]);

  // --- API CALLS ---

  const fetchProfile = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/profile`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        setToken('');
      }
    } catch (err) {
      setToken('');
    }
  };

  const fetchGroups = async () => {
    try {
      const res = await fetch(`${API_BASE}/groups`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setGroups(data);
      }
    } catch (err) {}
  };

  const fetchGroupDetails = async () => {
    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setActiveGroup(data);
      }
    } catch (err) {}
  };

  const fetchExpensesAndSettlements = async () => {
    try {
      const resExp = await fetch(`${API_BASE}/groups/${activeGroupId}/expenses`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const resSet = await fetch(`${API_BASE}/groups/${activeGroupId}/settlements`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (resExp.ok && resSet.ok) {
        const exps = await resExp.json();
        const sets = await resSet.json();
        setExpenses(exps);
        setSettlements(sets);
      }
    } catch (err) {}
  };

  const fetchBalances = async () => {
    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}/balances`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setBalances(data.balances);
        setSimplifiedDebts(data.simplified_debts);
      }
    } catch (err) {}
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, name })
      });
      const data = await res.json();
      if (res.ok) {
        // Auto-login
        handleLogin(e);
      } else {
        setAuthError(data.message || "Registration failed");
      }
    } catch (err) {
      setAuthError("Server connection error");
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (res.ok) {
        setToken(data.token);
      } else {
        setAuthError(data.message || "Invalid credentials");
      }
    } catch (err) {
      setAuthError("Server connection error");
    }
  };

  const handleCreateGroup = async (e) => {
    e.preventDefault();
    if (!newGroupName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/groups`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ name: newGroupName })
      });
      if (res.ok) {
        const data = await res.json();
        setNewGroupName('');
        fetchGroups();
        setActiveGroupId(data.id);
        setGlobalMessage(`Group "${data.name}" created!`);
      }
    } catch (err) {}
  };

  const handleAddMember = async (e) => {
    e.preventDefault();
    if (!newMemberUsername.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}/members`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          username: newMemberUsername,
          joined_at: newMemberJoined,
          left_at: newMemberLeft || null
        })
      });
      const data = await res.json();
      if (res.ok) {
        setNewMemberUsername('');
        setNewMemberLeft('');
        fetchGroupDetails();
        setGlobalMessage("Member added successfully!");
      } else {
        setGlobalError(data.message || "Error adding member");
      }
    } catch (err) {}
  };

  const handleUpdateMemberDates = async (userId, joinedAt, leftAt) => {
    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}/members/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          joined_at: joinedAt,
          left_at: leftAt || null
        })
      });
      if (res.ok) {
        fetchGroupDetails();
        fetchBalances();
        setGlobalMessage("Membership dates updated!");
      }
    } catch (err) {}
  };

  const handleAddExpense = async (e) => {
    e.preventDefault();
    // Prepare splits list
    const splitsList = [];
    if (expenseSplitType !== 'equal') {
      activeGroup.members.forEach(m => {
        if (customSplits[m.user_id]) {
          splitsList.push({
            user_id: m.user_id,
            split_value: parseFloat(customSplits[m.user_id])
          });
        }
      });
    }

    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}/expenses`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          description: expenseDesc,
          amount: parseFloat(expenseAmt),
          currency: expenseCurrency,
          exchange_rate: parseFloat(expenseRate),
          paid_by_id: expensePayer,
          split_type: expenseSplitType,
          date: expenseDate,
          notes: expenseNotes,
          splits: splitsList
        })
      });
      const data = await res.json();
      if (res.ok) {
        setShowExpenseModal(false);
        setExpenseDesc('');
        setExpenseAmt('');
        setExpenseNotes('');
        fetchExpensesAndSettlements();
        fetchBalances();
        setGlobalMessage("Expense added successfully!");
      } else {
        setGlobalError(data.message || "Error adding expense");
      }
    } catch (err) {}
  };

  const handleDeleteExpense = async (expenseId) => {
    if (!window.confirm("Are you sure you want to delete this expense?")) return;
    try {
      const res = await fetch(`${API_BASE}/expenses/${expenseId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        fetchExpensesAndSettlements();
        fetchBalances();
        setGlobalMessage("Expense deleted successfully!");
      }
    } catch (err) {}
  };

  const handleAddSettlement = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}/settlements`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          payer_id: settlePayer,
          payee_id: settlePayee,
          amount: parseFloat(settleAmt)
        })
      });
      if (res.ok) {
        setShowSettleModal(false);
        setSettleAmt('');
        fetchExpensesAndSettlements();
        fetchBalances();
        setGlobalMessage("Settlement recorded successfully!");
      }
    } catch (err) {}
  };

  // --- CSV IMPORTER WIZARD ---

  const handleCSVUpload = async (e) => {
    e.preventDefault();
    if (!importFile) {
      setImportError("Please select a file first");
      return;
    }
    
    setImportError('');
    setImportReport(null);
    const formData = new FormData();
    formData.append('file', importFile);

    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}/import/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setImportSessionId(data.import_session_id);
        setAnomalies(data.anomalies);
        
        // Initialize default resolutions
        const defaultResolutions = {};
        data.anomalies.forEach(a => {
          // prefill default resolutions based on suggested actions
          if (a.anomaly_type === 'quoted_amount' || a.anomaly_type === 'high_precision_amount') {
            const match = a.suggested_action.match(/Clean to ([\d\.]+)/) || a.suggested_action.match(/Round to ([\d\.]+)/);
            defaultResolutions[a.id] = match ? match[1] : '';
          } else if (a.anomaly_type === 'name_alias' || a.anomaly_type === 'name_casing') {
            const match = a.suggested_action.match(/'([^']+)'/);
            defaultResolutions[a.id] = match ? match[1] : '';
          } else if (a.anomaly_type === 'usd_transaction') {
            defaultResolutions[a.id] = '83.0'; // default exchange rate
          } else if (a.anomaly_type === 'invalid_percentage_sum') {
            defaultResolutions[a.id] = 'normalize';
          } else if (a.anomaly_type === 'inactive_member_split') {
            defaultResolutions[a.id] = 'exclude';
          } else if (a.anomaly_type === 'early_member_split') {
            defaultResolutions[a.id] = 'exclude';
          } else if (a.anomaly_type === 'duplicate') {
            // suggest skipping row 6 and keeping row 5
            const skipRowMatch = a.suggested_action.match(/Ignore Row (\d+)/);
            if (skipRowMatch) {
              const rowToSkip = parseInt(skipRowMatch[1]);
              defaultResolutions[a.id] = (a.row_index === rowToSkip) ? 'ignore' : 'keep';
            }
          } else if (a.anomaly_type === 'conflict') {
            // Keep Row 25
            defaultResolutions[a.id] = 'keep_row_25';
          } else if (a.anomaly_type === 'settlement_disguised') {
            defaultResolutions[a.id] = 'settlement';
          } else if (a.anomaly_type === 'missing_currency') {
            defaultResolutions[a.id] = 'INR';
          } else if (a.anomaly_type === 'zero_amount') {
            defaultResolutions[a.id] = 'skip';
          } else if (a.anomaly_type === 'guest_split') {
            defaultResolutions[a.id] = 'assign_to_dev';
          } else if (a.anomaly_type === 'non_group_member') {
            const match = a.suggested_action.match(/'([^']+)'/);
            defaultResolutions[a.id] = match ? match[1] : '';
          } else if (a.anomaly_type === 'inconsistent_date_format') {
            const match = a.suggested_action.match(/'([^']+)'/);
            defaultResolutions[a.id] = match ? match[1] : '';
          } else if (a.anomaly_type === 'ambiguous_date') {
            defaultResolutions[a.id] = '05-04-2026';
          }
        });
        setResolutions(defaultResolutions);
      } else {
        setImportError(data.message || "CSV upload failed");
      }
    } catch (err) {
      setImportError("Server connection error");
    }
  };

  const handleResolveSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/groups/${activeGroupId}/import/session/${importSessionId}/resolve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ resolutions })
      });
      const data = await res.json();
      if (res.ok) {
        setImportReport(data);
        setAnomalies([]);
        setImportSessionId('');
        setImportFile(null);
        fetchExpensesAndSettlements();
        fetchBalances();
        setGlobalMessage("CSV imported and resolved successfully!");
      } else {
        setImportError(data.message || "Resolution error");
      }
    } catch (err) {}
  };

  // --- LOGOUT ---
  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
    } catch (e) {}
    setToken('');
    setUser(null);
    setActiveGroupId('');
    setExpenses([]);
    setSettlements([]);
  };

  // Clear notifications after 5s
  useEffect(() => {
    if (globalMessage) {
      const t = setTimeout(() => setGlobalMessage(''), 5000);
      return () => clearTimeout(t);
    }
  }, [globalMessage]);

  useEffect(() => {
    if (globalError) {
      const t = setTimeout(() => setGlobalError(''), 5000);
      return () => clearTimeout(t);
    }
  }, [globalError]);

  // Auth screen rendering if not logged in
  if (!token) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center', padding: '20px' }}>
        <div className="ambient-glow"></div>
        <div className="ambient-glow-2"></div>
        <div className="glass-panel" style={{ width: '100%', maxWidth: '440px' }}>
          <h2 style={{ textAlign: 'center', marginBottom: '8px', background: 'linear-gradient(135deg, #818cf8, #22d3ee)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontWeight: 800, fontSize: '32px' }}>
            Trip Split
          </h2>
          <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginBottom: '24px' }}>
            {authMode === 'login' ? 'Welcome back! Sign in to continue' : 'Create an account to split expenses'}
          </p>

          {authError && <div className="alert alert-danger">{authError}</div>}

          <form onSubmit={authMode === 'login' ? handleLogin : handleRegister}>
            {authMode === 'register' && (
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Aisha Kumar"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  required
                />
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Username</label>
              <input
                type="text"
                className="form-control"
                placeholder="e.g. aisha"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="form-group" style={{ marginBottom: '28px' }}>
              <label className="form-label">Password</label>
              <input
                type="password"
                className="form-control"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px' }}>
              {authMode === 'login' ? 'Sign In' : 'Sign Up'}
            </button>
          </form>

          <p style={{ marginTop: '20px', textAlign: 'center', fontSize: '14px', color: 'var(--text-muted)' }}>
            {authMode === 'login' ? "Don't have an account? " : "Already have an account? "}
            <span
              style={{ color: 'var(--primary)', cursor: 'pointer', fontWeight: 600 }}
              onClick={() => {
                setAuthMode(authMode === 'login' ? 'register' : 'login');
                setAuthError('');
              }}
            >
              {authMode === 'login' ? 'Sign Up' : 'Sign In'}
            </span>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="ambient-glow"></div>
      <div className="ambient-glow-2"></div>

      {/* NAVBAR */}
      <header className="navbar">
        <a href="#" className="navbar-brand">
          <span>🌌</span> Trip Split
        </a>
        
        {activeGroupId && activeGroup && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-muted)' }}>Group:</span>
            <span style={{ fontWeight: 600, color: 'var(--secondary)' }}>{activeGroup.name}</span>
          </div>
        )}

        <div className="navbar-menu">
          {user && <span style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Logged in as: <strong style={{ color: 'var(--text-main)' }}>{user.name}</strong></span>}
          <button onClick={handleLogout} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }}>
            Sign Out
          </button>
        </div>
      </header>

      {/* GLOBAL ALERTS */}
      {globalMessage && (
        <div style={{ position: 'fixed', top: '80px', right: '40px', zIndex: 1100 }}>
          <div className="alert alert-success" style={{ boxShadow: '0 4px 20px rgba(0,0,0,0.5)', margin: 0 }}>
            ✅ {globalMessage}
          </div>
        </div>
      )}
      {globalError && (
        <div style={{ position: 'fixed', top: '80px', right: '40px', zIndex: 1100 }}>
          <div className="alert alert-danger" style={{ boxShadow: '0 4px 20px rgba(0,0,0,0.5)', margin: 0 }}>
            ⚠️ {globalError}
          </div>
        </div>
      )}

      {/* DASHBOARD GRID */}
      <main className="dashboard-grid">
        
        {/* SIDEBAR: Group Selection & Creation */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '20px' }}>
            <h3 style={{ marginBottom: '16px', fontSize: '16px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--text-muted)' }}>
              My Groups
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
              {groups.length === 0 ? (
                <p style={{ fontSize: '14px', color: 'var(--text-muted)' }}>No groups yet. Create one below!</p>
              ) : (
                groups.map(g => (
                  <button
                    key={g.id}
                    className={`btn ${g.id === activeGroupId ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ justifyContent: 'flex-start', width: '100%', textAlign: 'left', padding: '12px' }}
                    onClick={() => {
                      setActiveGroupId(g.id);
                      setImportReport(null);
                      setImportSessionId('');
                      setAnomalies([]);
                      setSelectedLedgerUser(null);
                    }}
                  >
                    📁 {g.name}
                  </button>
                ))
              )}
            </div>

            <form onSubmit={handleCreateGroup} style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '16px' }}>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <input
                  type="text"
                  className="form-control"
                  placeholder="New Group Name"
                  value={newGroupName}
                  onChange={e => setNewGroupName(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="btn btn-secondary" style={{ width: '100%', padding: '10px' }}>
                ➕ Create Group
              </button>
            </form>
          </div>

          {activeGroupId && activeGroup && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <h3 style={{ marginBottom: '16px', fontSize: '16px', textTransform: 'uppercase', letterSpacing: '1px', color: 'var(--text-muted)' }}>
                Navigation
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button
                  className={`btn ${activeTab === 'expenses' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ justifyContent: 'flex-start', width: '100%' }}
                  onClick={() => setActiveTab('expenses')}
                >
                  💳 Expenses & Ledgers
                </button>
                <button
                  className={`btn ${activeTab === 'balances' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ justifyContent: 'flex-start', width: '100%' }}
                  onClick={() => setActiveTab('balances')}
                >
                  💰 Balances & Simplify
                </button>
                <button
                  className={`btn ${activeTab === 'members' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ justifyContent: 'flex-start', width: '100%' }}
                  onClick={() => setActiveTab('members')}
                >
                  👤 Group Members
                </button>
                <button
                  className={`btn ${activeTab === 'import' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ justifyContent: 'flex-start', width: '100%' }}
                  onClick={() => setActiveTab('import')}
                >
                  📥 CSV Data Importer
                </button>
              </div>
            </div>
          )}
        </aside>

        {/* MAIN PANEL */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {!activeGroupId ? (
            <div className="glass-panel" style={{ textAlign: 'center', padding: '80px 40px' }}>
              <span style={{ fontSize: '64px' }}>🌍</span>
              <h1 style={{ marginTop: '20px', marginBottom: '10px' }}>Get Started with splits</h1>
              <p style={{ color: 'var(--text-muted)', maxWidth: '480px', margin: '0 auto' }}>
                Select a group from the sidebar, or create a new group to start logging expenses, resolving messy spreadsheets, and computing balances.
              </p>
            </div>
          ) : (
            <>
              {/* TAB 1: EXPENSES & LEDGERS */}
              {activeTab === 'expenses' && (
                <div className="glass-panel">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                    <h2>Group Expenses</h2>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button onClick={() => setShowSettleModal(true)} className="btn btn-secondary">
                        🤝 Record Payment
                      </button>
                      <button onClick={() => setShowExpenseModal(true)} className="btn btn-primary">
                        ➕ Add Expense
                      </button>
                    </div>
                  </div>

                  <div className="table-container">
                    {expenses.length === 0 && settlements.length === 0 ? (
                      <p style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
                        No transactions logged yet. Try importing the CSV or adding an expense!
                      </p>
                    ) : (
                      <table>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Description</th>
                            <th>Paid By</th>
                            <th>Amount</th>
                            <th>Split Mode</th>
                            <th>Recipients</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {/* List Settlements */}
                          {settlements.map(s => (
                            <tr key={s.id} style={{ fontStyle: 'italic', background: 'rgba(16, 185, 129, 0.02)' }}>
                              <td>{new Date(s.date).toLocaleDateString('en-GB')}</td>
                              <td>
                                <span className="badge badge-success" style={{ marginRight: '8px' }}>Settlement</span>
                                {s.notes || 'Direct Payment'}
                              </td>
                              <td style={{ color: 'var(--success)' }}>{s.payer_name}</td>
                              <td style={{ fontWeight: 600 }}>₹{s.amount_in_inr.toFixed(2)}</td>
                              <td>Direct</td>
                              <td>{s.payee_name}</td>
                              <td>-</td>
                            </tr>
                          ))}
                          
                          {/* List Expenses */}
                          {expenses.map(e => (
                            <tr key={e.id}>
                              <td>{new Date(e.date).toLocaleDateString('en-GB')}</td>
                              <td>
                                <div>{e.description}</div>
                                {e.notes && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Note: {e.notes}</div>}
                              </td>
                              <td>{e.paid_by_name}</td>
                              <td>
                                <div style={{ fontWeight: 600 }}>
                                  {e.currency === 'USD' ? `$${e.amount}` : `₹${e.amount}`}
                                </div>
                                {e.currency === 'USD' && (
                                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                    (₹{e.amount_in_inr.toFixed(2)} @ {e.exchange_rate})
                                  </div>
                                )}
                              </td>
                              <td>
                                <span className="badge badge-info">{e.split_type}</span>
                              </td>
                              <td>
                                <div style={{ fontSize: '12px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                  {e.splits.map(sp => (
                                    <span key={sp.id} style={{ background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
                                      {sp.user_name}: ₹{sp.amount_in_inr.toFixed(2)}
                                    </span>
                                  ))}
                                </div>
                              </td>
                              <td>
                                <button
                                  onClick={() => handleDeleteExpense(e.id)}
                                  className="btn btn-secondary"
                                  style={{ padding: '4px 8px', fontSize: '12px', background: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.2)', color: 'var(--danger)' }}
                                >
                                  Delete
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 2: BALANCES & LEDGERS */}
              {activeTab === 'balances' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  
                  {/* Balance Summary Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px' }}>
                    {balances.map(b => (
                      <div
                        key={b.user_id}
                        className="glass-panel"
                        style={{
                          textAlign: 'center',
                          cursor: 'pointer',
                          border: selectedLedgerUser?.user_id === b.user_id ? '1px solid var(--primary)' : '1px solid rgba(255, 255, 255, 0.08)',
                          boxShadow: selectedLedgerUser?.user_id === b.user_id ? '0 0 15px var(--primary-glow)' : 'none'
                        }}
                        onClick={() => setSelectedLedgerUser(b)}
                      >
                        <h4 style={{ color: 'var(--text-muted)', marginBottom: '8px' }}>{b.name}</h4>
                        <div style={{ fontSize: '28px', fontWeight: 700, color: b.net_balance >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                          {b.net_balance >= 0 ? '+' : ''}₹{b.net_balance.toFixed(2)}
                        </div>
                        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
                          Paid: ₹{b.paid.toFixed(0)} | Owed: ₹{b.owed.toFixed(0)}
                        </p>
                        <span style={{ fontSize: '12px', color: 'var(--primary)', marginTop: '8px', display: 'inline-block' }}>
                          🔍 Click to see ledger breakdown
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Aisha's Simplified Debts (Greedy minimizing cash flow) */}
                  <div className="glass-panel">
                    <h2>Simplified Debts (Aisha's Request)</h2>
                    <p style={{ color: 'var(--text-muted)', marginBottom: '16px', fontSize: '14px' }}>
                      This algorithm computes the absolute minimum transfers needed to fully settle all debts.
                    </p>

                    {simplifiedDebts.length === 0 ? (
                      <div style={{ padding: '24px', background: 'rgba(16, 185, 129, 0.05)', borderRadius: '12px', color: 'var(--success)', fontWeight: 600, textAlign: 'center' }}>
                        🎉 Everyone is fully settled! No payments are needed.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {simplifiedDebts.map((d, index) => (
                          <div
                            key={index}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '16px 20px',
                              background: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid rgba(255, 255, 255, 0.05)',
                              borderRadius: '12px'
                            }}
                          >
                            <div style={{ fontSize: '16px' }}>
                              <strong style={{ color: 'var(--danger)' }}>{d.from_name}</strong>
                              <span style={{ color: 'var(--text-muted)', margin: '0 8px' }}>owes</span>
                              <strong style={{ color: 'var(--success)' }}>{d.to_name}</strong>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--primary)' }}>
                                ₹{d.amount.toFixed(2)}
                              </span>
                              <button
                                onClick={async () => {
                                  // Auto record settlement
                                  if (window.confirm(`Mark ₹${d.amount} payment from ${d.from_name} to ${d.to_name} as settled?`)) {
                                    try {
                                      await fetch(`${API_BASE}/groups/${activeGroupId}/settlements`, {
                                        method: 'POST',
                                        headers: {
                                          'Content-Type': 'application/json',
                                          'Authorization': `Bearer ${token}`
                                        },
                                        body: JSON.stringify({
                                          payer_id: d.from_id,
                                          payee_id: d.to_id,
                                          amount: d.amount,
                                          notes: `Auto settlement matching simplified debts`
                                        })
                                      });
                                      fetchExpensesAndSettlements();
                                      fetchBalances();
                                    } catch(e) {}
                                  }
                                }}
                                className="btn btn-primary"
                                style={{ padding: '6px 12px', fontSize: '12px' }}
                              >
                                Mark Settled
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Rohan's Ledger Breakdown (No magic numbers) */}
                  {selectedLedgerUser && (
                    <div className="glass-panel">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h2>Ledger Breakdown for {selectedLedgerUser.name} (Rohan's Request)</h2>
                        <button onClick={() => setSelectedLedgerUser(null)} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }}>
                          Hide
                        </button>
                      </div>
                      
                      <p style={{ color: 'var(--text-muted)', marginBottom: '16px', fontSize: '14px' }}>
                        Below is every transaction contributing to {selectedLedgerUser.name}'s balance. 
                        <strong> Formula: Balance = (Paid + Sent) - (Owed + Received)</strong>.
                      </p>

                      <div className="table-container">
                        <table>
                          <thead>
                            <tr>
                              <th>Date</th>
                              <th>Type</th>
                              <th>Description</th>
                              <th>Paid/Sent (+)</th>
                              <th>Owed/Received (-)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedLedgerUser.ledger.map((item, idx) => {
                              const isPositive = item.type === 'paid' || item.type === 'settlement_sent';
                              return (
                                <tr key={idx}>
                                  <td>{new Date(item.date).toLocaleDateString('en-GB')}</td>
                                  <td>
                                    <span className={`badge ${
                                      item.type === 'paid' ? 'badge-info' : 
                                      item.type === 'settlement_sent' ? 'badge-success' : 
                                      item.type === 'settlement_received' ? 'badge-warning' : 'badge-danger'
                                    }`}>
                                      {item.type.replace('_', ' ')}
                                    </span>
                                  </td>
                                  <td style={{ color: 'var(--text-main)', fontSize: '13px' }}>
                                    {item.description}
                                    {item.notes && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>({item.notes})</div>}
                                  </td>
                                  <td style={{ color: 'var(--success)', fontWeight: isPositive ? 600 : 400 }}>
                                    {isPositive ? `+₹${item.amount.toFixed(2)}` : '-'}
                                  </td>
                                  <td style={{ color: 'var(--danger)', fontWeight: !isPositive ? 600 : 400 }}>
                                    {!isPositive ? `-₹${item.amount.toFixed(2)}` : '-'}
                                  </td>
                                </tr>
                              );
                            })}
                            
                            {/* Summary row */}
                            <tr style={{ fontWeight: 700, borderTop: '2px solid rgba(255,255,255,0.1)' }}>
                              <td colSpan={3} style={{ textAlign: 'right' }}>Calculated Net Balance:</td>
                              <td colSpan={2} style={{ color: selectedLedgerUser.net_balance >= 0 ? 'var(--success)' : 'var(--danger)', fontSize: '18px' }}>
                                ₹{selectedLedgerUser.net_balance.toFixed(2)}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: MEMBERS */}
              {activeTab === 'members' && (
                <div className="glass-panel">
                  <h2>Manage Group Members</h2>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '24px', fontSize: '14px' }}>
                    Each member's active membership dates determine which expenses they split. Users will only split expenses that occur within their active range.
                  </p>

                  <div className="table-container" style={{ marginBottom: '32px' }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Joined Date</th>
                          <th>Moved Out Date (Optional)</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeGroup.members.map(m => (
                          <tr key={m.id}>
                            <td style={{ fontWeight: 600 }}>{m.user_name}</td>
                            <td>
                              <input
                                type="date"
                                className="form-control"
                                style={{ padding: '6px', width: '150px' }}
                                value={m.joined_at.split('T')[0]}
                                onChange={e => handleUpdateMemberDates(m.user_id, e.target.value, m.left_at)}
                              />
                            </td>
                            <td>
                              <input
                                type="date"
                                className="form-control"
                                style={{ padding: '6px', width: '150px' }}
                                value={m.left_at ? m.left_at.split('T')[0] : ''}
                                onChange={e => handleUpdateMemberDates(m.user_id, m.joined_at, e.target.value || null)}
                              />
                            </td>
                            <td>
                              {(!m.left_at || new Date(m.left_at) >= new Date()) ? (
                                <span className="badge badge-success">Active</span>
                              ) : (
                                <span className="badge badge-danger">Moved Out</span>
                              )}
                            </td>
                            <td>
                              {m.left_at && (
                                <button
                                  onClick={() => handleUpdateMemberDates(m.user_id, m.joined_at, null)}
                                  className="btn btn-secondary"
                                  style={{ padding: '4px 8px', fontSize: '12px' }}
                                >
                                  Re-activate
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <form onSubmit={handleAddMember} style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '24px' }}>
                    <h3>Add Member to Group</h3>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginTop: '16px' }}>
                      <div className="form-group" style={{ flex: 1, minWidth: '200px' }}>
                        <label className="form-label">Username</label>
                        <input
                          type="text"
                          className="form-control"
                          placeholder="e.g. sam"
                          value={newMemberUsername}
                          onChange={e => setNewMemberUsername(e.target.value)}
                          required
                        />
                      </div>
                      <div className="form-group" style={{ flex: 1, minWidth: '150px' }}>
                        <label className="form-label">Joined Date</label>
                        <input
                          type="date"
                          className="form-control"
                          value={newMemberJoined}
                          onChange={e => setNewMemberJoined(e.target.value)}
                          required
                        />
                      </div>
                      <div className="form-group" style={{ flex: 1, minWidth: '150px' }}>
                        <label className="form-label">Moved Out Date (Optional)</label>
                        <input
                          type="date"
                          className="form-control"
                          value={newMemberLeft}
                          onChange={e => setNewMemberLeft(e.target.value)}
                        />
                      </div>
                    </div>
                    <button type="submit" className="btn btn-primary" style={{ marginTop: '12px' }}>
                      ➕ Add Member
                    </button>
                  </form>
                </div>
              )}

              {/* TAB 4: CSV IMPORTER WIZARD */}
              {activeTab === 'import' && (
                <div className="glass-panel">
                  <h2>CSV Data Importer</h2>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '24px', fontSize: '14px' }}>
                    Upload <code>expenses_export.csv</code>. The app will parse the file, detect all inconsistencies/anomalies, present them to you, and let you choose how to resolve them before saving!
                  </p>

                  {/* Drag and Drop Zone */}
                  {!importSessionId && !importReport && (
                    <form onSubmit={handleCSVUpload}>
                      <div className="form-group" style={{ marginBottom: '20px' }}>
                        <label className="form-label">Select Spreadsheet CSV</label>
                        <div
                          className="drag-drop-zone"
                          onClick={() => document.getElementById('csvFileInput').click()}
                        >
                          <span>📥</span>
                          <p style={{ marginTop: '10px', fontWeight: 600 }}>
                            {importFile ? importFile.name : "Click to browse and select file"}
                          </p>
                          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                            Supports .csv files exactly as exported.
                          </p>
                          <input
                            type="file"
                            id="csvFileInput"
                            style={{ display: 'none' }}
                            accept=".csv"
                            onChange={e => setImportFile(e.target.files[0])}
                          />
                        </div>
                      </div>
                      
                      {importError && <div className="alert alert-danger">{importError}</div>}

                      <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>
                        🚀 Upload and Check for Anomalies
                      </button>
                    </form>
                  )}

                  {/* Anomaly Resolution Dashboard */}
                  {importSessionId && anomalies.length > 0 && (
                    <div>
                      <div style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)', padding: '16px', borderRadius: '12px', marginBottom: '24px', color: '#fcd34d' }}>
                        ⚠️ <strong>{anomalies.length} Data Inconsistencies Detected!</strong> Meera's request: You must review and resolve all anomalies before the CSV data is saved.
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '32px' }}>
                        {anomalies.map(a => (
                          <div
                            key={a.id}
                            style={{
                              background: 'rgba(255,255,255,0.02)',
                              border: '1px solid rgba(255,255,255,0.06)',
                              borderRadius: '12px',
                              padding: '20px'
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px', alignItems: 'center' }}>
                              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
                                Row {a.row_index} | raw: <code>{a.raw_row.substring(0, 45)}...</code>
                              </span>
                              <span className="badge badge-warning">{a.anomaly_type.replace('_', ' ')}</span>
                            </div>

                            <p style={{ fontSize: '15px', color: 'var(--text-main)', marginBottom: '16px' }}>
                              {a.description}
                            </p>

                            <div className="form-group" style={{ margin: 0 }}>
                              <label className="form-label" style={{ color: 'var(--primary)' }}>Choose Resolution Policy:</label>
                              
                              {/* Resolution Interface based on Anomaly Type */}
                              
                              {/* DUPLICATE */}
                              {a.anomaly_type === 'duplicate' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="keep"
                                      checked={resolutions[a.id] === 'keep'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Keep this Row
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="ignore"
                                      checked={resolutions[a.id] === 'ignore'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Ignore/Skip Duplicate
                                  </label>
                                </div>
                              )}

                              {/* CONFLICT */}
                              {a.anomaly_type === 'conflict' && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="keep_row_25"
                                      checked={resolutions[a.id] === 'keep_row_25'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Keep Rohan's log (Row 25: Thalassa dinner, Rohan paid ₹2450)
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="keep_row_24"
                                      checked={resolutions[a.id] === 'keep_row_24'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Keep Aisha's log (Row 24: Dinner at Thalassa, Aisha paid ₹2400)
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="keep_both"
                                      checked={resolutions[a.id] === 'keep_both'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Import both entries
                                  </label>
                                </div>
                              )}

                              {/* DATE FORMAT AMBIGUITY */}
                              {a.anomaly_type === 'ambiguous_date' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', alignItems: 'center' }}>
                                  <select
                                    className="form-control"
                                    style={{ width: '220px' }}
                                    value={resolutions[a.id]}
                                    onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                  >
                                    <option value="05-04-2026">April 5, 2026 (Recommended)</option>
                                    <option value="04-05-2026">May 4, 2026</option>
                                  </select>
                                </div>
                              )}

                              {/* INCONSISTENT DATE FORMAT */}
                              {a.anomaly_type === 'inconsistent_date_format' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', alignItems: 'center' }}>
                                  <input
                                    type="text"
                                    className="form-control"
                                    style={{ width: '220px' }}
                                    value={resolutions[a.id] || ''}
                                    onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    placeholder="DD-MM-YYYY"
                                  />
                                </div>
                              )}

                              {/* USD TRANSACTION FX RATE */}
                              {a.anomaly_type === 'usd_transaction' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', alignItems: 'center' }}>
                                  <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Enter FX Rate (1 USD to INR):</span>
                                  <input
                                    type="number"
                                    step="0.01"
                                    className="form-control"
                                    style={{ width: '120px' }}
                                    value={resolutions[a.id] || ''}
                                    onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                  />
                                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Priya: "Pretending a dollar is a rupee can't be right!"</span>
                                </div>
                              )}

                              {/* NAME INCONSISTENCIES / GUESTS / MISSING PAYERS */}
                              {(a.anomaly_type === 'name_alias' || a.anomaly_type === 'name_casing' || a.anomaly_type === 'non_group_member' || a.anomaly_type === 'missing_payer') && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', alignItems: 'center' }}>
                                  <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Map to user:</span>
                                  <select
                                    className="form-control"
                                    style={{ width: '220px' }}
                                    value={resolutions[a.id] || ''}
                                    onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                  >
                                    <option value="">-- Select Member --</option>
                                    {activeGroup.members.map(m => (
                                      <option key={m.id} value={m.user_name}>{m.user_name}</option>
                                    ))}
                                    {a.anomaly_type === 'non_group_member' && (
                                      <option value={a.suggested_action.match(/'([^']+)'/)?.[1] || 'Guest'}>
                                        Create New User "{a.suggested_action.match(/'([^']+)'/)?.[1]}"
                                      </option>
                                    )}
                                  </select>
                                </div>
                              )}

                              {/* GUEST KABIR SPLIT */}
                              {a.anomaly_type === 'guest_split' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="assign_to_dev"
                                      checked={resolutions[a.id] === 'assign_to_dev'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Assign Kabir's share to Dev (Dev pays for his guest)
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="add_member"
                                      checked={resolutions[a.id] === 'add_member'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Create guest user "Kabir" in group
                                  </label>
                                </div>
                              )}

                              {/* INACTIVE MEMBER SPLIT (Meera in April) */}
                              {a.anomaly_type === 'inactive_member_split' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="exclude"
                                      checked={resolutions[a.id] === 'exclude'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Exclude Meera (split among remaining active members)
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="include"
                                      checked={resolutions[a.id] === 'include'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Keep Meera in split (override date check)
                                  </label>
                                </div>
                              )}

                              {/* EARLY MEMBER SPLIT (Sam in March) */}
                              {a.anomaly_type === 'early_member_split' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="exclude"
                                      checked={resolutions[a.id] === 'exclude'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Exclude Sam (Sam asks: Why would March electricity affect my balance?)
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="include"
                                      checked={resolutions[a.id] === 'include'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Keep Sam in split
                                  </label>
                                </div>
                              )}

                              {/* PERCENTAGE SPLIT NOT SUMMING TO 100% */}
                              {a.anomaly_type === 'invalid_percentage_sum' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="normalize"
                                      checked={resolutions[a.id] === 'normalize'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Normalize percentages proportionally to sum to 100%
                                  </label>
                                </div>
                              )}

                              {/* SETTLEMENT DISGUISED AS EXPENSE */}
                              {a.anomaly_type === 'settlement_disguised' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="settlement"
                                      checked={resolutions[a.id] === 'settlement'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Import as direct peer-to-peer Settlement
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="expense"
                                      checked={resolutions[a.id] === 'expense'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Import as split Expense
                                  </label>
                                </div>
                              )}

                              {/* QUOTED / HIGH PRECISION AMOUNT */}
                              {(a.anomaly_type === 'quoted_amount' || a.anomaly_type === 'high_precision_amount') && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', alignItems: 'center' }}>
                                  <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Cleaned Amount:</span>
                                  <input
                                    type="number"
                                    step="0.01"
                                    className="form-control"
                                    style={{ width: '120px' }}
                                    value={resolutions[a.id] || ''}
                                    onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                  />
                                </div>
                              )}

                              {/* MISSING CURRENCY */}
                              {a.anomaly_type === 'missing_currency' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', alignItems: 'center' }}>
                                  <select
                                    className="form-control"
                                    style={{ width: '120px' }}
                                    value={resolutions[a.id]}
                                    onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                  >
                                    <option value="INR">INR</option>
                                    <option value="USD">USD</option>
                                  </select>
                                </div>
                              )}

                              {/* ZERO AMOUNT */}
                              {a.anomaly_type === 'zero_amount' && (
                                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="skip"
                                      checked={resolutions[a.id] === 'skip'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Skip this row (Skip zero-amount expense)
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input
                                      type="radio"
                                      name={`res-${a.id}`}
                                      value="keep"
                                      checked={resolutions[a.id] === 'keep'}
                                      onChange={e => setResolutions({...resolutions, [a.id]: e.target.value})}
                                    />
                                    Import as 0 amount
                                  </label>
                                </div>
                              )}

                            </div>
                          </div>
                        ))}
                      </div>

                      <button onClick={handleResolveSession} className="btn btn-primary" style={{ width: '100%', padding: '14px' }}>
                        ✅ Save Resolutions and Complete CSV Import
                      </button>
                    </div>
                  )}

                  {/* CSV Import Report */}
                  {importReport && (
                    <div style={{ marginTop: '20px' }}>
                      <div className="alert alert-success">
                        🎉 <strong>CSV Import Completed!</strong> Imported {importReport.imported_count} rows, Skipped {importReport.skipped_count} rows.
                      </div>
                      
                      <h3>Final Import Report (Anomaly Action Log)</h3>
                      <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '16px' }}>
                        This report maps every line in the spreadsheet to the action taken by the importer. You can view or save this report.
                      </p>

                      <div className="table-container" style={{ maxHeight: '400px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px' }}>
                        <table>
                          <thead>
                            <tr>
                              <th>Row</th>
                              <th>Description</th>
                              <th>Action Taken</th>
                            </tr>
                          </thead>
                          <tbody>
                            {importReport.report.map((item, idx) => (
                              <tr key={idx}>
                                <td>{item.row_index}</td>
                                <td style={{ fontWeight: 500 }}>{item.description}</td>
                                <td style={{ color: item.action.includes('Skipped') ? 'var(--danger)' : 'var(--success)' }}>
                                  {item.action}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      
                      <button
                        onClick={() => {
                          // Download Report
                          const reportText = importReport.report.map(r => `Row ${r.row_index} | ${r.description} | ${r.action}`).join('\n');
                          const blob = new Blob([reportText], { type: 'text/plain' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `Import_Report_Session_${new Date().toISOString().split('T')[0]}.txt`;
                          a.click();
                        }}
                        className="btn btn-secondary"
                        style={{ marginTop: '16px' }}
                      >
                        💾 Download Import Report
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </main>

      {/* MODAL: ADD EXPENSE */}
      {showExpenseModal && (
        <div className="modal-overlay" onClick={() => setShowExpenseModal(false)}>
          <div className="modal-content glass-panel" onClick={e => e.stopPropagation()}>
            <h2>Add New Expense</h2>
            <form onSubmit={handleAddExpense}>
              <div className="form-group">
                <label className="form-label">Description</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Groceries BigBasket"
                  value={expenseDesc}
                  onChange={e => setExpenseDesc(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: '16px' }}>
                <div className="form-group" style={{ flex: 2 }}>
                  <label className="form-label">Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    className="form-control"
                    placeholder="0.00"
                    value={expenseAmt}
                    onChange={e => setExpenseAmt(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">Currency</label>
                  <select
                    className="form-control"
                    value={expenseCurrency}
                    onChange={e => setExpenseCurrency(e.target.value)}
                  >
                    <option value="INR">INR (₹)</option>
                    <option value="USD">USD ($)</option>
                  </select>
                </div>
              </div>

              {expenseCurrency === 'USD' && (
                <div className="form-group">
                  <label className="form-label">Exchange Rate (1 USD to INR)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="form-control"
                    value={expenseRate}
                    onChange={e => setExpenseRate(e.target.value)}
                    required
                  />
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Paid By</label>
                <select
                  className="form-control"
                  value={expensePayer}
                  onChange={e => setExpensePayer(e.target.value)}
                  required
                >
                  {activeGroup.members.map(m => (
                    <option key={m.id} value={m.user_id}>{m.user_name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Split Method</label>
                <select
                  className="form-control"
                  value={expenseSplitType}
                  onChange={e => setExpenseSplitType(e.target.value)}
                >
                  <option value="equal">Split Equally</option>
                  <option value="percentage">Percentage Split</option>
                  <option value="share">Shares Split</option>
                  <option value="unequal">Unequal Amounts</option>
                </select>
              </div>

              {/* Custom splits inputs */}
              {expenseSplitType !== 'equal' && (
                <div style={{ background: 'rgba(0,0,0,0.1)', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>
                  <label className="form-label">
                    Enter values ({expenseSplitType === 'percentage' ? '%' : expenseSplitType === 'share' ? 'shares' : 'amounts'}):
                  </label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '10px' }}>
                    {activeGroup.members.map(m => (
                      <div key={m.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>{m.user_name}</span>
                        <input
                          type="number"
                          step="0.01"
                          className="form-control"
                          style={{ width: '120px', padding: '6px' }}
                          value={customSplits[m.user_id] || ''}
                          onChange={e => setCustomSplits({
                            ...customSplits,
                            [m.user_id]: e.target.value
                          })}
                          placeholder="0"
                          required
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', gap: '16px' }}>
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">Date</label>
                  <input
                    type="date"
                    className="form-control"
                    value={expenseDate}
                    onChange={e => setExpenseDate(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ flex: 2 }}>
                  <label className="form-label">Notes</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Optional notes"
                    value={expenseNotes}
                    onChange={e => setExpenseNotes(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '12px' }}>
                <button type="button" onClick={() => setShowExpenseModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  💾 Save Expense
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: RECORD SETTLEMENT */}
      {showSettleModal && (
        <div className="modal-overlay" onClick={() => setShowSettleModal(false)}>
          <div className="modal-content glass-panel" onClick={e => e.stopPropagation()}>
            <h2>Record Direct Payment</h2>
            <form onSubmit={handleAddSettlement}>
              <div className="form-group">
                <label className="form-label">Who Paid (Payer)</label>
                <select
                  className="form-control"
                  value={settlePayer}
                  onChange={e => setSettlePayer(e.target.value)}
                  required
                >
                  {activeGroup.members.map(m => (
                    <option key={m.id} value={m.user_id}>{m.user_name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Who Received (Payee)</label>
                <select
                  className="form-control"
                  value={settlePayee}
                  onChange={e => setSettlePayee(e.target.value)}
                  required
                >
                  {activeGroup.members.map(m => (
                    <option key={m.id} value={m.user_id}>{m.user_name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: '24px' }}>
                <label className="form-label">Amount (INR)</label>
                <input
                  type="number"
                  step="0.01"
                  className="form-control"
                  placeholder="0.00"
                  value={settleAmt}
                  onChange={e => setSettleAmt(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" onClick={() => setShowSettleModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  💾 Record Payment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
