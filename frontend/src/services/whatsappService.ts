// whatsappService.ts
import axios from 'axios';

const API_BASE = '/api/whatsapp';

export const fetchConversations = async () => {
  const response = await axios.get(`${API_BASE}/conversations`);
  return response.data;
};

export const syncConversations = async (limit: number = 20) => {
  const response = await axios.post(`${API_BASE}/sync`, { limit });
  return response.data;
};

export const fetchConversationDetails = async (id: number, messageLimit: number = 20) => {
  const response = await axios.get(`${API_BASE}/conversation/${id}?message_limit=${messageLimit}`);
  return response.data;
};

export const assessConversation = async (id: number) => {
  const response = await axios.post(`${API_BASE}/conversation/${id}/assess`);
  return response.data;
};

export const generateResponse = async (id: number) => {
  const response = await axios.post(`${API_BASE}/conversation/${id}/generate`);
  return response.data;
};

export const sendResponse = async (conversationId: number, responseId: number) => {
  const response = await axios.post(`${API_BASE}/conversation/${conversationId}/send`, { response_id: responseId });
  return response.data;
};

export const getAuthQRCode = async () => {
  const response = await axios.post(`${API_BASE}/auth`);
  return response.data.qr_code;
};

export const checkAuthStatus = async () => {
  const response = await axios.get(`${API_BASE}/auth/status`);
  return response.data.authenticated;
};