import { 
  type AnalysisResponse, 
  type DashboardStats, 
  type HistoryItem, 
  type ComplianceRule, 
  type AuthUser, 
  type TrendPoint, 
  type StatusBreakdown, 
  type PenaltyEstimate, 
  type ShowCauseNotice, 
  type ProductInfo, 
  type ComplianceResult, 
  type RuleTestRequest, 
  type RuleTestResponse, 
  type RuleConflictItem, 
  type ScoringConfiguration, 
  type ScoreHistoryEntry, 
  type ProductRiskHistory, 
  type BatchRiskDistribution,
  type PreprintUploadResponse,
  type PreprintAnalysisResponse,
  type PreprintApprovalRequest,
  type ArtworkDocument,
  type VersionComparisonRequest,
  type VersionComparisonResult,
  type VersionTimelineEvent,
  type OfficerDashboardSummary,
  type ReviewItem,
  type ReviewDetailResponse,
  type AIvsHumanComparison,
  type ReviewHistoryEvent,
  type ClaimAnalysisResult
} from '../types';
import { getApiHost, setApiHost, getApiBaseUrl, getAssetUrl, isNativePlatform } from '../config/api';

// Re-export so existing imports from 'services/api' keep working
export { getApiHost, setApiHost, getApiBaseUrl, getAssetUrl, isNativePlatform };

const BASE_URL = {
  valueOf: () => getApiBaseUrl(),
  toString: () => getApiBaseUrl()
};

const TOKEN_KEY = 'metrcheck-token';

export const tokenStore = {
  get: (): string | null => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (token: string) => {
    try { localStorage.setItem(TOKEN_KEY, token); } catch { /* ignore */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  },
};

function authHeaders(): Record<string, string> {
  const token = tokenStore.get();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJSON<T>(url: string, options?: RequestInit & { _timeout?: number }): Promise<T> {
  const isAuthOrCritical = url.includes('/auth/') || url.includes('/analyze');
  const headers: Record<string, string> = {
    // Bypass ngrok free-tier browser-warning interstitial (serves HTML instead
    // of JSON for browser-like User-Agents, e.g. the Android WebView).
    'ngrok-skip-browser-warning': 'true',
    'Accept': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
    ...authHeaders(),
  };

  // Prevent ANY relative fallback on native mobile APK when no host is configured.
  // Relative URLs (e.g. '/api/...', '/auth/login') resolve to the WebView's own
  // origin (https://localhost) and return index.html — not JSON.
  if (!url || (url.startsWith('/') && isNativePlatform() && !getApiHost())) {
    const errorMsg = 'No backend server configured. Please configure your MetrCheck AI server address in Server Settings.';
    console.error(`[MetrCheck API] Blocked relative request without configured host on mobile: ${url}`);
    throw new Error(errorMsg);
  }

  const timeoutMs = options?._timeout ?? 30000;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  // Safe request logging (URL and method only — never credentials or payload)
  if (isAuthOrCritical) {
    console.log(`[MetrCheck API] Request: ${options?.method || 'GET'} ${url}`);
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers, signal: controller.signal });
  } catch (err: any) {
    clearTimeout(timeout);
    if (err.name === 'AbortError') {
      if (isAuthOrCritical) console.error(`[MetrCheck API] Request timed out (${timeoutMs}ms) for ${url}`);
      throw new Error('Request timed out. The backend server may be busy or unreachable.');
    }
    const host = getApiHost();
    const hostDesc = host ? `(${host})` : '(No server configured)';
    if (isAuthOrCritical) {
      console.error(`[MetrCheck API] Network connection failed for ${url}:`, err.message);
    }
    if (!host && isNativePlatform()) {
      throw new Error('No backend server configured. Please tap "Server Settings" on the login screen to set your server URL.');
    }
    throw new Error(
      `Cannot connect to backend server ${hostDesc}. Please verify that the FastAPI server is running (port 8000) and your device is on the same network.`
    );
  } finally {
    clearTimeout(timeout);
  }

  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();

  // Safe response debug logging (status, content-type, sanitized preview)
  if (isAuthOrCritical) {
    const preview = text.length > 120 ? text.substring(0, 120).replace(/\r?\n|\r/g, ' ') + '…' : text.replace(/\r?\n|\r/g, ' ');
    const sanitizedPreview = preview
      .replace(/"token"\s*:\s*"[^"]+"/g, '"token":"[REDACTED]"')
      .replace(/"password"\s*:\s*"[^"]+"/g, '"password":"[REDACTED]"');
    console.log(`[MetrCheck API] Status: ${response.status} ${response.statusText}`);
    console.log(`[MetrCheck API] Content-Type: ${contentType || '[NONE]'}`);
    console.log(`[MetrCheck API] Body Preview: ${sanitizedPreview}`);
  }

  const isJsonHeader = contentType.toLowerCase().includes('application/json');
  const isHtml = text.trim().toLowerCase().startsWith('<!doctype') || text.trim().toLowerCase().startsWith('<html') || text.trim().startsWith('<');

  let data: any = null;
  // NEVER blindly call response.json() if Content-Type is not application/json or if body is HTML
  if (isJsonHeader || (!isHtml && (text.trim().startsWith('{') || text.trim().startsWith('[')))) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  // Handle HTML document fallback (e.g. Capacitor WebView routing to index.html instead of FastAPI)
  if (isHtml || (!isJsonHeader && data === null)) {
    const host = getApiHost();
    console.error(`[MetrCheck API] Expected JSON from ${url}, but received non-JSON (${contentType || 'unknown'}). Status: ${response.status}`);
    if (isHtml) {
      throw new Error(
        `Backend/API unavailable: Server returned an HTML web page instead of JSON (${response.status} ${response.statusText}). ` +
        `Current server URL: "${host || 'none'}". Verify that the URL points to the FastAPI backend (e.g. port 8000), NOT the web frontend.`
      );
    }
    throw new Error(
      `Backend/API unavailable: Server returned unexpected content-type "${contentType || 'unknown'}" (${response.status} ${response.statusText}).`
    );
  }

  if (!response.ok) {
    const detail = data?.detail || (text.startsWith('<') ? `Server error (${response.status}). Check your server connection.` : text);
    if (response.status === 401) {
      if (!url.includes('/auth/login')) {
        tokenStore.clear();
      }
      throw new Error(detail || 'Session expired. Please log in again.');
    }
    if (response.status === 403) {
      throw new Error(detail || 'Access denied. You do not have permission for this action.');
    }
    if (response.status === 404) {
      throw new Error(detail || 'Resource not found. Please verify the API endpoint.');
    }
    if (response.status === 422) {
      throw new Error(detail || 'Invalid request. Please check your input.');
    }
    if (response.status === 429) {
      throw new Error(detail || 'Too many requests. Please wait a moment and try again.');
    }
    if (response.status >= 500) {
      throw new Error(detail || 'Server error. Please try again later.');
    }
    throw new Error(detail || `Request failed (${response.status}).`);
  }

  if (data === null) {
    throw new Error(
      'Received unexpected response from server. Please verify the Server URL in Settings.'
    );
  }

  return data as T;
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────
  login: (username: string, password: string): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),

  forgotPassword: (identifier: string): Promise<{ message: string; dev_token?: string }> =>
    fetchJSON<{ message: string; dev_token?: string }>(`${BASE_URL}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier }),
    }),

  verifyResetToken: (token: string): Promise<{ valid: boolean; username?: string }> =>
    fetchJSON<{ valid: boolean; username?: string }>(`${BASE_URL}/auth/verify-reset-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  resetPassword: (token: string, new_password: string): Promise<{ message: string }> =>
    fetchJSON<{ message: string }>(`${BASE_URL}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password }),
    }),

  verifyInvitation: (token: string): Promise<import('../types').InvitationVerification> =>
    fetchJSON<import('../types').InvitationVerification>(`${BASE_URL}/auth/verify-invitation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  activateAccount: (token: string, password: string): Promise<{ message: string; username: string }> =>
    fetchJSON<{ message: string; username: string }>(`${BASE_URL}/auth/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    }),

  register: (body: { username: string; email: string; password: string; full_name?: string; role?: string }): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  getMe: (): Promise<AuthUser> => fetchJSON<AuthUser>(`${BASE_URL}/auth/me`),

  updateMyEmail: (email: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/me/email`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }),

  // ── Administration API (/api/admin) ──────────────────────────────────
  adminGetUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/admin/users`),

  adminProvisionUser: (body: {
    full_name?: string;
    username: string;
    email: string;
    role: string;
    jurisdiction?: string;
  }): Promise<{ message: string; user: AuthUser; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; user: AuthUser; dev_invitation_token?: string }>(`${BASE_URL}/admin/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  adminResendInvitation: (username: string): Promise<{ message: string; username: string; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; username: string; dev_invitation_token?: string }>(
      `${BASE_URL}/admin/users/${encodeURIComponent(username)}/resend-invitation`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    ),

  adminSuspendUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/suspend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminReactivateUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/reactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminChangeRole: (username: string, role: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/change-role`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    }),

  adminDeleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/admin/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

  adminGetAuditLogs: (limit = 50): Promise<import('../types').AccountAuditLog[]> =>
    fetchJSON<import('../types').AccountAuditLog[]>(`${BASE_URL}/admin/audit-logs?limit=${limit}`),

  // Legacy User APIs
  getUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/auth/users`),

  createUser: (body: { username: string; email?: string; password: string; full_name?: string; jurisdiction?: string; role?: string }): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateUser: (
    username: string,
    updates: { full_name?: string; jurisdiction?: string; email?: string; role?: string; new_password?: string }
  ): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    }),

  deleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

  // ── Analyses ──────────────────────────────────────────────────────────
  analyzeProduct: async (file: File): Promise<AnalysisResponse> => {
    const formData = new FormData();
    formData.append('files', file);
    formData.append('labels', JSON.stringify(['Front']));
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeProducts: async (items: { file: File; label: string }[]): Promise<AnalysisResponse> => {
    const formData = new FormData();
    const labels: string[] = [];
    items.forEach((item) => {
      formData.append('files', item.file);
      labels.push(item.label || 'Front');
    });
    formData.append('labels', JSON.stringify(labels));
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeText: (text: string): Promise<AnalysisResponse> =>
    fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  checkListing: (payload: {
    mode: 'URL' | 'RAW_TEXT' | 'STRUCTURED';
    url?: string;
    raw_text?: string;
    structured_data?: Record<string, any>;
    package_analysis_id?: string;
  }): Promise<import('../types').ListingCheckResponse> =>
    fetchJSON<import('../types').ListingCheckResponse>(`${BASE_URL}/listing/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getListingPackageTargets: (): Promise<{ targets: { analysis_id: string; product_name: string; created_at: string; score: number; status: string }[]; total: number }> =>
    fetchJSON<{ targets: { analysis_id: string; product_name: string; created_at: string; score: number; status: string }[]; total: number }>(`${BASE_URL}/listing/package-targets`),


  getDashboardStats: (): Promise<DashboardStats> => {
    return fetchJSON<DashboardStats>(`${BASE_URL}/stats`);
  },

  getTrends: (days = 14): Promise<TrendPoint[]> => {
    return fetchJSON<TrendPoint[]>(`${BASE_URL}/stats/trends?days=${days}`);
  },

  getStatusBreakdown: (): Promise<StatusBreakdown[]> => {
    return fetchJSON<StatusBreakdown[]>(`${BASE_URL}/stats/by-status`);
  },

  getHistory: (): Promise<HistoryItem[]> => {
    return fetchJSON<HistoryItem[]>(`${BASE_URL}/history`);
  },

  searchHistory: (q: string, status = 'ALL', limit = 50): Promise<{ items: HistoryItem[]; total: number }> => {
    const params = new URLSearchParams({ q, status, limit: String(limit) });
    return fetchJSON<{ items: HistoryItem[]; total: number }>(`${BASE_URL}/history/search?${params}`);
  },

  getAnalysis: (id: string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/history/${id}`);
  },

  deleteAnalysis: (id: string): Promise<{ message: string; id: string }> => {
    return fetchJSON<{ message: string; id: string }>(`${BASE_URL}/history/${id}`, {
      method: 'DELETE',
    });
  },

  clearHistory: (): Promise<{ message: string; deleted_count: number }> => {
    return fetchJSON<{ message: string; deleted_count: number }>(`${BASE_URL}/history`, {
      method: 'DELETE',
    });
  },

  // ── Enforcement (officer/admin only) ──────────────────────────────────
  estimatePenalty: (analysisId: string): Promise<PenaltyEstimate> => {
    return fetchJSON<PenaltyEstimate>(`${BASE_URL}/enforcement/penalty`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  showCauseNotice: (analysisId: string): Promise<ShowCauseNotice> => {
    return fetchJSON<ShowCauseNotice>(`${BASE_URL}/enforcement/notice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  // ── Demo / reference / misc ───────────────────────────────────────────
  getDemoCases: (): Promise<import('../types').DemoCaseMeta[]> => {
    return fetchJSON<import('../types').DemoCaseMeta[]>(`${BASE_URL}/demo/cases`);
  },

  getDemoCase: (caseNum: number | string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/demo/${caseNum}`);
  },

  getComplianceRules: (params?: { category?: string; domain?: string; version?: string }): Promise<ComplianceRule[]> => {
    const query = new URLSearchParams();
    if (params?.category) query.append('category', params.category);
    if (params?.domain) query.append('domain', params.domain);
    if (params?.version) query.append('version', params.version);
    const qs = query.toString();
    return fetchJSON<ComplianceRule[]>(`${BASE_URL}/compliance/rules${qs ? `?${qs}` : ''}`);
  },

  getComplianceRuleDetail: (ruleId: string): Promise<ComplianceRule> => {
    return fetchJSON<ComplianceRule>(`${BASE_URL}/compliance/rules/${encodeURIComponent(ruleId)}`);
  },

  testComplianceRule: (req: RuleTestRequest): Promise<RuleTestResponse> => {
    return fetchJSON<RuleTestResponse>(`${BASE_URL}/compliance/test-rule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
  },

  getAnalysisConflicts: (analysisId: string): Promise<{ analysis_id: string; conflicts: RuleConflictItem[] }> => {
    return fetchJSON<{ analysis_id: string; conflicts: RuleConflictItem[] }>(`${BASE_URL}/compliance/conflicts/${encodeURIComponent(analysisId)}`);
  },

  getHealth: (): Promise<any> => {
    return fetchJSON<any>(`${BASE_URL}/health`);
  },
  getReportUrl: (id: string, lang?: string): string => {
    const params = new URLSearchParams();
    if (lang && lang !== 'en') {
      params.append('lang', lang);
    }
    const token = tokenStore.get();
    if (token) {
      params.append('token', token);
    }
    const qs = params.toString();
    return `${BASE_URL}/report/${id}${qs ? `?${qs}` : ''}`;
  },
  getCsvReportUrl: (id: string): string => {
    const token = tokenStore.get();
    return `${BASE_URL}/report/${id}/csv${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
  getXlsxReportUrl: (id: string): string => {
    const token = tokenStore.get();
    return `${BASE_URL}/report/${id}/xlsx${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
  getJsonReportUrl: (id: string): string => {
    const token = tokenStore.get();
    return `${BASE_URL}/report/${id}/json${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
  getAssetUrl: (url: string): string => {
    return getAssetUrl(url);
  },
  extractText: (text: string): Promise<ProductInfo> =>
    fetchJSON<ProductInfo>(`${BASE_URL}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  checkCompliance: (info: ProductInfo): Promise<ComplianceResult> =>
    fetchJSON<ComplianceResult>(`${BASE_URL}/compliance/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(info),
    }),

  // ── Scoring & Risk (Section 7) ──────────────────────────────────────────
  getScoringConfig: (): Promise<ScoringConfiguration> =>
    fetchJSON<ScoringConfiguration>(`${BASE_URL}/scoring/config`),

  updateScoringConfig: (config: ScoringConfiguration): Promise<ScoringConfiguration> =>
    fetchJSON<ScoringConfiguration>(`${BASE_URL}/scoring/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  getScoreHistory: (analysisId: string): Promise<ScoreHistoryEntry> =>
    fetchJSON<ScoreHistoryEntry>(`${BASE_URL}/scoring/history/${encodeURIComponent(analysisId)}`),

  getProductRiskHistory: (productName: string): Promise<ProductRiskHistory> =>
    fetchJSON<ProductRiskHistory>(`${BASE_URL}/scoring/product/${encodeURIComponent(productName)}/history`),

  getBatchRiskDistribution: (ownerUserId?: string): Promise<BatchRiskDistribution> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<BatchRiskDistribution>(`${BASE_URL}/scoring/batch-distribution${qs}`);
  },

  // ── Pre-Print Packaging Compliance (Section 8) ──────────────────────────
  uploadArtwork: async (file: File, parentArtworkId?: string, iterationNumber = 1): Promise<PreprintUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (parentArtworkId) {
      formData.append('parent_artwork_id', parentArtworkId);
    }
    formData.append('iteration_number', String(iterationNumber));
    return fetchJSON<PreprintUploadResponse>(`${BASE_URL}/preprint/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeArtwork: (artworkId: string, productName?: string, category?: string): Promise<PreprintAnalysisResponse> => {
    const params = new URLSearchParams();
    if (productName) params.append('product_name', productName);
    if (category) params.append('category', category);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return fetchJSON<PreprintAnalysisResponse>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/analyze${qs}`, {
      method: 'POST',
    });
  },

  getArtwork: (artworkId: string): Promise<ArtworkDocument> =>
    fetchJSON<ArtworkDocument>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}`),

  uploadArtworkCorrection: async (artworkId: string, file: File): Promise<PreprintAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    return fetchJSON<PreprintAnalysisResponse>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/correction-upload`, {
      method: 'POST',
      body: formData,
    });
  },

  submitArtworkApproval: (artworkId: string, req: PreprintApprovalRequest): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  listArtworks: (ownerUserId?: string): Promise<{ artworks: ArtworkDocument[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<{ artworks: ArtworkDocument[]; total: number }>(`${BASE_URL}/preprint${qs}`);
  },

  deleteArtwork: (artworkId: string): Promise<{ success: boolean; message: string }> =>
    fetchJSON<{ success: boolean; message: string }>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}`, {
      method: 'DELETE',
    }),

  // ── Section 9 Version Comparison ─────────────────────────────────────────
  compareVersions: (req: VersionComparisonRequest): Promise<VersionComparisonResult> =>
    fetchJSON<VersionComparisonResult>(`${BASE_URL}/versions/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  getComparison: (comparisonId: string): Promise<VersionComparisonResult> =>
    fetchJSON<VersionComparisonResult>(`${BASE_URL}/versions/comparisons/${encodeURIComponent(comparisonId)}`),

  listComparisons: (ownerUserId?: string, limit = 50): Promise<{ comparisons: VersionComparisonResult[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}&limit=${limit}` : `?limit=${limit}`;
    return fetchJSON<{ comparisons: VersionComparisonResult[]; total: number }>(`${BASE_URL}/versions/comparisons${qs}`);
  },

  getVersionTimeline: (entityId: string): Promise<{ entity_id: string; events: VersionTimelineEvent[]; total: number }> =>
    fetchJSON<{ entity_id: string; events: VersionTimelineEvent[]; total: number }>(`${BASE_URL}/versions/timeline/${encodeURIComponent(entityId)}`),

  getVersionTargets: (ownerUserId?: string): Promise<{ targets: any[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<{ targets: any[]; total: number }>(`${BASE_URL}/versions/targets${qs}`);
  },

  // ── Section 10 Human Verification / Officer Workflow ─────────────────────
  getReviewDashboard: (): Promise<OfficerDashboardSummary> =>
    fetchJSON<OfficerDashboardSummary>(`${BASE_URL}/reviews/dashboard`),

  getReviewQueue: (status?: string, assignedOfficer?: string, riskLevel?: string, limit = 100): Promise<ReviewItem[]> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (assignedOfficer) params.append('assigned_officer', assignedOfficer);
    if (riskLevel) params.append('risk_level', riskLevel);
    params.append('limit', String(limit));
    return fetchJSON<ReviewItem[]>(`${BASE_URL}/reviews/queue?${params.toString()}`);
  },

  getAvailableOfficers: (): Promise<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }> =>
    fetchJSON<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }>(`${BASE_URL}/reviews/officers`),

  getReviewDetails: (reviewId: string): Promise<ReviewDetailResponse> =>
    fetchJSON<ReviewDetailResponse>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}`),

  assignReview: (reviewId: string, assignedOfficer: string, comments?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_officer: assignedOfficer, comments }),
    }),

  acceptReview: (reviewId: string, comments?: string, finalStatus?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comments, final_status: finalStatus }),
    }),

  rejectReview: (reviewId: string, rejectionReason: string, comments: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rejection_reason: rejectionReason, comments }),
    }),

  correctReviewField: (
    reviewId: string, 
    fieldName: string, 
    fieldLabel: string, 
    correctedValue: string, 
    reason?: string, 
    evidenceId?: string
  ): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/correct-field`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        field_name: fieldName,
        field_label: fieldLabel,
        corrected_value: correctedValue,
        reason,
        evidence_id: evidenceId
      }),
    }),

  addReviewEvidence: (
    reviewId: string,
    data: {
      image_index: number;
      image_label: string;
      text: string;
      bbox?: number[];
      linked_rule_id: string;
      linked_field: string;
      comments?: string;
    }
  ): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/evidence/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  removeReviewEvidence: (reviewId: string, evidenceId: string, reason: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/evidence/remove`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ evidence_id: evidenceId, reason }),
    }),

  addReviewComment: (reviewId: string, text: string, commentType = 'GENERAL'): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, comment_type: commentType }),
    }),

  escalateReview: (reviewId: string, escalationReason: string, comments?: string, escalationTarget?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/escalate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        escalation_reason: escalationReason,
        comments,
        escalation_target: escalationTarget
      }),
    }),

  reopenReview: (reviewId: string, reopenReason: string, comments?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/reopen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reopen_reason: reopenReason, comments }),
    }),

  getAIvsHumanDiff: (reviewId: string): Promise<AIvsHumanComparison> =>
    fetchJSON<AIvsHumanComparison>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/ai-vs-human`),

  getReviewHistory: (reviewId: string): Promise<{ review_id: string; history: ReviewHistoryEvent[]; total: number }> =>
    fetchJSON<{ review_id: string; history: ReviewHistoryEvent[]; total: number }>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/history`),

  // ── Misleading Claims Detection ─────────────────────────────────────────
  analyzeClaims: (data: { analysis_id?: string; text?: string; product_info?: any }): Promise<ClaimAnalysisResult> =>
    fetchJSON<ClaimAnalysisResult>(`${BASE_URL}/claims/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  getClaimRules: (category?: string, riskLevel?: string): Promise<any[]> => {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (riskLevel) params.append('risk_level', riskLevel);
    const qs = params.toString();
    return fetchJSON<any[]>(`${BASE_URL}/claims/rules${qs ? `?${qs}` : ''}`);
  },

  getClaimRule: (ruleId: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/claims/rules/${encodeURIComponent(ruleId)}`),

  getAnalysisClaims: (analysisId: string): Promise<ClaimAnalysisResult> =>
    fetchJSON<ClaimAnalysisResult>(`${BASE_URL}/claims/${encodeURIComponent(analysisId)}`),
};

export default api;
