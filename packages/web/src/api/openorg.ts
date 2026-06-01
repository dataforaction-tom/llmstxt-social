/**
 * API client + TanStack Query hooks for Open Org admin and public routes.
 *
 * Public routes (no auth):
 *   GET /open-org/{org_id}/profile.json
 *   GET /open-org/{org_id}/strategies/{slug}.json
 *   GET /open-org/{org_id}/ideas/{slug}.json
 *
 * Admin routes (cookie auth + OrgAdmin grant):
 *   GET / PUT /api/open-org/{org_id}/profile.md
 *   GET / PUT /api/open-org/{org_id}/strategies/{slug}.md
 *   GET / PUT /api/open-org/{org_id}/ideas/{slug}.md
 *   GET      /api/open-org/{org_id}/history
 */

import axios, { AxiosError } from 'axios';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

export type SchemaKind = 'profile' | 'strategy' | 'idea';

export interface MarkdownResponse {
  markdown: string;
  org_id: string;
  schema_kind: SchemaKind;
  // Only set for profiles. Drives the Publish/Unpublish toggle on the editor.
  published?: boolean;
}

export interface PublishResponse {
  org_id: string;
  published: boolean;
  submission_task_id: string | null;
}

export interface UnpublishResponse {
  org_id: string;
  published: boolean;
  delete_task_id: string | null;
}

export class OpenOrgPublishError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(detail || `publish failed: HTTP ${status}`);
    this.name = 'OpenOrgPublishError';
    this.status = status;
    this.detail = detail;
  }
}

export interface SaveResponse {
  saved: boolean;
  org_id: string;
  schema_kind: SchemaKind;
}

export interface ValidationFieldError {
  path: string;
  message: string;
}

export interface ValidationErrorPayload {
  errors: ValidationFieldError[];
}

export class OpenOrgValidationError extends Error {
  readonly errors: ValidationFieldError[];
  constructor(errors: ValidationFieldError[]) {
    super(`${errors.length} validation error(s)`);
    this.name = 'OpenOrgValidationError';
    this.errors = errors;
  }
}

function asValidationError(err: unknown): OpenOrgValidationError | null {
  if (!(err instanceof AxiosError) || err.response?.status !== 400) return null;
  const detail = err.response.data?.detail;
  if (detail && Array.isArray(detail.errors)) {
    return new OpenOrgValidationError(detail.errors);
  }
  return null;
}

// --- public reads (no auth) ----------------------------------------------

export async function fetchPublicProfile(orgId: string): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/open-org/${orgId}/profile.json`);
  return data;
}

export async function fetchPublicStrategy(
  orgId: string,
  slug: string,
): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/open-org/${orgId}/strategies/${slug}.json`);
  return data;
}

export async function fetchPublicIdea(
  orgId: string,
  slug: string,
): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/open-org/${orgId}/ideas/${slug}.json`);
  return data;
}

export interface PublicRecordSummary {
  slug: string;
  themes: string[];
  status?: string;
  summary?: string;
}

export async function fetchPublicStrategies(orgId: string): Promise<PublicRecordSummary[]> {
  const { data } = await api.get(`/open-org/${orgId}/strategies`);
  return data;
}

export async function fetchPublicIdeas(orgId: string): Promise<PublicRecordSummary[]> {
  const { data } = await api.get(`/open-org/${orgId}/ideas`);
  return data;
}

// --- admin (auth required) ----------------------------------------------

export async function fetchProfileMarkdown(orgId: string): Promise<MarkdownResponse> {
  const { data } = await api.get(`/api/open-org/${orgId}/profile.md`);
  return data;
}

export async function saveProfileMarkdown(
  orgId: string,
  markdown: string,
): Promise<SaveResponse> {
  try {
    const { data } = await api.put(`/api/open-org/${orgId}/profile.md`, { markdown });
    return data;
  } catch (err) {
    const validation = asValidationError(err);
    if (validation) throw validation;
    throw err;
  }
}

export async function fetchStrategyMarkdown(
  orgId: string,
  slug: string,
): Promise<MarkdownResponse> {
  const { data } = await api.get(`/api/open-org/${orgId}/strategies/${slug}.md`);
  return data;
}

export async function saveStrategyMarkdown(
  orgId: string,
  slug: string,
  markdown: string,
): Promise<SaveResponse> {
  try {
    const { data } = await api.put(
      `/api/open-org/${orgId}/strategies/${slug}.md`,
      { markdown },
    );
    return data;
  } catch (err) {
    const validation = asValidationError(err);
    if (validation) throw validation;
    throw err;
  }
}

export async function fetchIdeaMarkdown(
  orgId: string,
  slug: string,
): Promise<MarkdownResponse> {
  const { data } = await api.get(`/api/open-org/${orgId}/ideas/${slug}.md`);
  return data;
}

export async function saveIdeaMarkdown(
  orgId: string,
  slug: string,
  markdown: string,
): Promise<SaveResponse> {
  try {
    const { data } = await api.put(`/api/open-org/${orgId}/ideas/${slug}.md`, {
      markdown,
    });
    return data;
  } catch (err) {
    const validation = asValidationError(err);
    if (validation) throw validation;
    throw err;
  }
}

export async function publishProfile(orgId: string): Promise<PublishResponse> {
  try {
    const { data } = await api.post(`/api/open-org/${orgId}/publish`);
    return data;
  } catch (err) {
    if (err instanceof AxiosError && err.response) {
      const detail = err.response.data?.detail;
      throw new OpenOrgPublishError(
        err.response.status,
        typeof detail === 'string' ? detail : 'publish failed',
      );
    }
    throw err;
  }
}

export async function unpublishProfile(orgId: string): Promise<UnpublishResponse> {
  try {
    const { data } = await api.post(`/api/open-org/${orgId}/unpublish`);
    return data;
  } catch (err) {
    if (err instanceof AxiosError && err.response) {
      const detail = err.response.data?.detail;
      throw new OpenOrgPublishError(
        err.response.status,
        typeof detail === 'string' ? detail : 'unpublish failed',
      );
    }
    throw err;
  }
}

export interface RecordPublishResponse {
  org_id: string;
  slug: string;
  schema_kind: 'strategy' | 'idea';
  published: boolean;
}

export interface GenerateProfileResponse {
  org_id: string;
  profile_id: string;
  generation_status: string;
  task_id: string | null;
}

export class OpenOrgGenerateError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(detail || `generate failed: HTTP ${status}`);
    this.name = 'OpenOrgGenerateError';
    this.status = status;
    this.detail = detail;
  }
}

export async function generateProfile(
  charityNumber: string,
  ownerEmail: string,
): Promise<GenerateProfileResponse> {
  try {
    const { data } = await api.post('/api/open-org/generate', {
      charity_number: charityNumber,
      owner_email: ownerEmail,
    });
    return data;
  } catch (err) {
    if (err instanceof AxiosError && err.response) {
      const raw = err.response.data?.detail;
      const detail =
        typeof raw === 'string'
          ? raw
          : Array.isArray(raw)
          ? raw.map((d: { msg?: string }) => d.msg ?? '').join('; ')
          : 'generate failed';
      throw new OpenOrgGenerateError(err.response.status, detail);
    }
    throw err;
  }
}

async function postRecordPublish(
  orgId: string,
  kind: 'strategies' | 'ideas',
  slug: string,
  action: 'publish' | 'unpublish',
): Promise<RecordPublishResponse> {
  try {
    const { data } = await api.post(
      `/api/open-org/${orgId}/${kind}/${slug}/${action}`,
    );
    return data;
  } catch (err) {
    if (err instanceof AxiosError && err.response) {
      const detail = err.response.data?.detail;
      throw new OpenOrgPublishError(
        err.response.status,
        typeof detail === 'string' ? detail : `${action} failed`,
      );
    }
    throw err;
  }
}

export const publishStrategy = (orgId: string, slug: string) =>
  postRecordPublish(orgId, 'strategies', slug, 'publish');

export const unpublishStrategy = (orgId: string, slug: string) =>
  postRecordPublish(orgId, 'strategies', slug, 'unpublish');

export const publishIdea = (orgId: string, slug: string) =>
  postRecordPublish(orgId, 'ideas', slug, 'publish');

export const unpublishIdea = (orgId: string, slug: string) =>
  postRecordPublish(orgId, 'ideas', slug, 'unpublish');

export interface HistoryEntry {
  id: string;
  parent_kind: string;
  parent_id: string;
  created_at: string;
  created_by_user_id: string | null;
}

export async function fetchHistory(orgId: string): Promise<HistoryEntry[]> {
  const { data } = await api.get(`/api/open-org/${orgId}/history`);
  return data.versions;
}

// --- hooks ---------------------------------------------------------------

export function useProfileMarkdown(orgId: string) {
  return useQuery({
    queryKey: ['openorg', 'profile-md', orgId],
    queryFn: () => fetchProfileMarkdown(orgId),
    enabled: Boolean(orgId),
  });
}

export function useSaveProfile(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (markdown: string) => saveProfileMarkdown(orgId, markdown),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'profile-md', orgId] });
      qc.invalidateQueries({ queryKey: ['openorg', 'history', orgId] });
    },
  });
}

export function usePublishProfile(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => publishProfile(orgId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'profile-md', orgId] });
    },
  });
}

export function useUnpublishProfile(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unpublishProfile(orgId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'profile-md', orgId] });
    },
  });
}

export function useStrategyMarkdown(orgId: string, slug: string) {
  return useQuery({
    queryKey: ['openorg', 'strategy-md', orgId, slug],
    queryFn: () => fetchStrategyMarkdown(orgId, slug),
    enabled: Boolean(orgId && slug),
  });
}

export function useSaveStrategy(orgId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (markdown: string) => saveStrategyMarkdown(orgId, slug, markdown),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'strategy-md', orgId, slug] });
    },
  });
}

export function usePublishStrategy(orgId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => publishStrategy(orgId, slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'strategy-md', orgId, slug] });
    },
  });
}

export function useUnpublishStrategy(orgId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unpublishStrategy(orgId, slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'strategy-md', orgId, slug] });
    },
  });
}

export function useIdeaMarkdown(orgId: string, slug: string) {
  return useQuery({
    queryKey: ['openorg', 'idea-md', orgId, slug],
    queryFn: () => fetchIdeaMarkdown(orgId, slug),
    enabled: Boolean(orgId && slug),
  });
}

export function useSaveIdea(orgId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (markdown: string) => saveIdeaMarkdown(orgId, slug, markdown),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'idea-md', orgId, slug] });
    },
  });
}

export function usePublishIdea(orgId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => publishIdea(orgId, slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'idea-md', orgId, slug] });
    },
  });
}

export function useUnpublishIdea(orgId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unpublishIdea(orgId, slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'idea-md', orgId, slug] });
    },
  });
}

export function useHistory(orgId: string) {
  return useQuery({
    queryKey: ['openorg', 'history', orgId],
    queryFn: () => fetchHistory(orgId),
    enabled: Boolean(orgId),
  });
}

export interface RestoreResponse {
  org_id: string;
  restored_from_version: string;
  new_version_id: string;
}

export async function restoreVersion(
  orgId: string,
  versionId: string,
): Promise<RestoreResponse> {
  try {
    const { data } = await api.post(
      `/api/open-org/${orgId}/history/${versionId}/restore`,
    );
    return data;
  } catch (err) {
    const validation = asValidationError(err);
    if (validation) throw validation;
    throw err;
  }
}

export function useRestoreVersion(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) => restoreVersion(orgId, versionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['openorg', 'profile-md', orgId] });
      qc.invalidateQueries({ queryKey: ['openorg', 'history', orgId] });
    },
  });
}

// --- discovery (public, no auth) ----------------------------------------

export interface ThemeEntry {
  key: string;
  label: string;
  description: string;
}

export interface DiscoveryRow {
  org_id: string;
  name: string;
  summary: string | null;
  themes: string[];
  primary_area: string | null;
  primary_area_code: string | null;
  geolocation: { lat: number; lon: number } | null;
  profile_url: string;
  source: 'local' | 'federated';
}

export interface DiscoveryPage {
  results: DiscoveryRow[];
  next_cursor: string | null;
}

export interface DiscoveryFilters {
  theme?: string;
  areaCode?: string;
  q?: string;
}

export async function fetchThemes(): Promise<ThemeEntry[]> {
  const { data } = await api.get('/api/open-org/themes');
  return data;
}

export async function fetchDiscoveryPage(
  filters: DiscoveryFilters,
  cursor: string | null = null,
  limit = 20,
): Promise<DiscoveryPage> {
  const params: Record<string, string | number> = { limit };
  if (filters.theme) params.theme = filters.theme;
  if (filters.areaCode) params.area_code = filters.areaCode;
  if (filters.q) params.q = filters.q;
  if (cursor) params.cursor = cursor;
  const { data } = await api.get('/api/open-org/discover', { params });
  return data;
}

export function useThemes() {
  return useQuery({
    queryKey: ['openorg', 'themes'],
    queryFn: fetchThemes,
    staleTime: 30 * 60 * 1000, // 30 minutes; matches server Cache-Control
  });
}

export function useDiscoveryFirstPage(filters: DiscoveryFilters, limit = 20) {
  return useQuery({
    queryKey: ['openorg', 'discover', filters, limit],
    queryFn: () => fetchDiscoveryPage(filters, null, limit),
  });
}

// --- idea browser (cross-org) ---------------------------------------------

export interface IdeaRow {
  org_id: string;
  org_name: string;
  slug: string;
  summary: string | null;
  themes: string[];
  status: string | null;
  primary_area: string | null;
  cost_lower: number | null;
  cost_upper: number | null;
  cost_currency: string | null;
  idea_url: string;
  profile_url: string;
}

export interface IdeaPage {
  results: IdeaRow[];
  next_cursor: string | null;
}

export interface IdeaFilters {
  theme?: string;
  status?: string;
  q?: string;
  costMax?: number;
}

export async function fetchIdeasPage(
  filters: IdeaFilters,
  cursor: string | null = null,
  limit = 20,
): Promise<IdeaPage> {
  const params: Record<string, string | number> = { limit };
  if (filters.theme) params.theme = filters.theme;
  if (filters.status) params.status = filters.status;
  if (filters.q) params.q = filters.q;
  if (filters.costMax !== undefined) params.cost_max = filters.costMax;
  if (cursor) params.cursor = cursor;
  const { data } = await api.get('/api/open-org/discover/ideas', { params });
  return data;
}

export function useIdeasFirstPage(filters: IdeaFilters, limit = 20) {
  return useQuery({
    queryKey: ['openorg', 'discover-ideas', filters, limit],
    queryFn: () => fetchIdeasPage(filters, null, limit),
  });
}

// --- chat creator (Step 8) ---------------------------------------------

export type CreatorKind = 'strategy' | 'idea';

export interface CreatorSessionInit {
  session_id: string;
  kind: CreatorKind;
  org_id: string;
  current_markdown: string | null;
}

export interface CreatorSessionDetail {
  session_id: string;
  kind: CreatorKind;
  org_id: string;
  conversation_history: { role: 'user' | 'assistant'; content: string }[];
  current_markdown: string | null;
  expires_at: string;
}

export interface FinalizeResponse {
  kind: CreatorKind;
  org_id: string;
  slug: string;
}

export async function createCreatorSession(
  orgId: string,
  kind: CreatorKind,
  upload?: File,
): Promise<CreatorSessionInit> {
  const url = `/api/open-org/${orgId}/create/${kind}`;
  if (upload) {
    const form = new FormData();
    form.append('upload', upload);
    const { data } = await api.post(url, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  }
  const { data } = await api.post(url);
  return data;
}

export async function fetchCreatorSession(sessionId: string): Promise<CreatorSessionDetail> {
  const { data } = await api.get(`/api/open-org/create/${sessionId}`);
  return data;
}

export async function finalizeCreatorSession(sessionId: string): Promise<FinalizeResponse> {
  const { data } = await api.post(`/api/open-org/create/${sessionId}/finalize`);
  return data;
}

/**
 * Stream a chat-creator message via SSE. Calls ``onDelta`` for each text chunk
 * and ``onDone`` with the final state (current_markdown + usage) when the
 * server emits the ``event: done`` frame.
 *
 * Uses ``fetch`` directly because EventSource doesn't support POST bodies.
 * Parses the wire format ourselves: each frame is
 *     event: <name>\n
 *     data: <json>\n\n
 */
export async function streamCreatorMessage(
  sessionId: string,
  content: string,
  onDelta: (text: string) => void,
  onDone: (payload: { current_markdown: string | null; usage?: unknown }) => void,
): Promise<void> {
  const baseUrl = API_BASE_URL || '';
  const response = await fetch(`${baseUrl}/api/open-org/create/${sessionId}/message`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    throw new Error(`creator stream failed: HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error('creator stream returned no body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  let reading = true;
  while (reading) {
    const { value, done } = await reader.read();
    if (done) {
      reading = false;
      continue;
    }
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let blank = buffer.indexOf('\n\n');
    while (blank !== -1) {
      const frame = buffer.slice(0, blank);
      buffer = buffer.slice(blank + 2);
      const event = parseSseFrame(frame);
      if (event) {
        if (event.name === 'delta' && typeof event.data.text === 'string') {
          onDelta(event.data.text);
        } else if (event.name === 'done') {
          onDone(event.data as { current_markdown: string | null; usage?: unknown });
        }
      }
      blank = buffer.indexOf('\n\n');
    }
  }
}

function parseSseFrame(frame: string): { name: string; data: Record<string, unknown> } | null {
  const lines = frame.split('\n');
  let name = 'message';
  const dataParts: string[] = [];
  for (const line of lines) {
    if (line.startsWith('event:')) {
      name = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataParts.push(line.slice(5).trim());
    }
  }
  if (!dataParts.length) return null;
  try {
    return { name, data: JSON.parse(dataParts.join('\n')) };
  } catch {
    return null;
  }
}
