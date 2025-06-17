import { apiClient } from './api/client';
import {
  RaciMatrix,
  CreateRaciMatrixPayload,
  UpdateRaciMatrixPayload,
  CreateRaciMatrixResponse,
  RaciMatrixType
} from '@/types/entities';

export const raciMatrixService = {
  // Get all RACI matrices
  async getAllMatrices(): Promise<RaciMatrix[]> {
    const response = await apiClient.get('/api/v1/raci-matrices/');
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Get a specific RACI matrix by ID
  async getMatrixById(matrixId: string): Promise<RaciMatrix> {
    const response = await apiClient.get(`/api/v1/raci-matrices/${matrixId}`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Get RACI matrices by type
  async getMatricesByType(matrixType: RaciMatrixType): Promise<RaciMatrix[]> {
    const response = await apiClient.get(`/api/v1/raci-matrices/type/${matrixType}`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Create a new RACI matrix
  async createMatrix(payload: CreateRaciMatrixPayload): Promise<CreateRaciMatrixResponse> {
    const response = await apiClient.post('/api/v1/raci-matrices/', payload);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Update an existing RACI matrix
  async updateMatrix(matrixId: string, payload: UpdateRaciMatrixPayload): Promise<CreateRaciMatrixResponse> {
    const response = await apiClient.put(`/api/v1/raci-matrices/${matrixId}`, payload);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Delete a RACI matrix
  async deleteMatrix(matrixId: string): Promise<{ message: string }> {
    const response = await apiClient.delete(`/api/v1/raci-matrices/${matrixId}`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  },

  // Validate a RACI matrix
  async validateMatrix(matrixId: string): Promise<{ is_valid: boolean; errors: string[] }> {
    const response = await apiClient.post(`/api/v1/raci-matrices/${matrixId}/validate`);
    if (response.error) {
      throw new Error(response.error);
    }
    return response.data;
  }
};

export default raciMatrixService; 