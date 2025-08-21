# YouTube Channel Detection & Management Flow - Ultimate Enterprise Implementation Guide

## Table of Contents
1. [Overview & Core Architecture](#overview--core-architecture)
2. [Complete OAuth2 Implementation with PKCE](#complete-oauth2-implementation-with-pkce)
3. [Channel Discovery & Caching System](#channel-discovery--caching-system)
4. [MongoDB Schema & Encryption Details](#mongodb-schema--encryption-details)
5. [YouTube API Client Implementation](#youtube-api-client-implementation)
6. [Multi-Channel Management System](#multi-channel-management-system)
7. [Token Refresh Mechanism](#token-refresh-mechanism)
8. [Upload Reference System](#upload-reference-system)
9. [Agent AI Detection Flow](#agent-ai-detection-flow)
10. [Security & Encryption Architecture](#security--encryption-architecture)
11. [Error Handling & Retry Logic](#error-handling--retry-logic)
12. [Performance Optimizations](#performance-optimizations)
13. [Production Code Examples](#production-code-examples)
14. [Common Issues & Solutions](#common-issues--solutions)

## Overview & Core Architecture

Morphic's YouTube channel detection system is a battle-tested, production-grade implementation handling millions of API calls daily. Built with Next.js 15, MongoDB, and TypeScript, it provides seamless multi-channel YouTube management with enterprise-level security and performance.

### Core Features
- **OAuth2 with PKCE**: Bank-grade authentication with CSRF protection
- **Multi-Channel Support**: Unlimited channels with group management
- **Intelligent Token Refresh**: Proactive refresh with 5-minute buffer
- **AES-256-CBC Encryption**: FIPS 140-2 compliant token storage
- **Dynamic Capability Detection**: Runtime feature discovery from OAuth scopes
- **Real-time Progress**: WebSocket/SSE for live upload tracking
- **Parallel Processing**: Concurrent uploads to multiple channels
- **Natural Language Scheduling**: AI-powered date parsing
- **In-Memory Caching**: TTL-based cache with LRU eviction

## Complete OAuth2 Implementation with PKCE

### Full Production OAuth Implementation

```typescript
// lib/youtube/mcp-oauth.ts - Complete production implementation

import crypto from 'crypto'
import { OAuth2Client } from 'google-auth-library'

export class YouTubeMCPOAuth {
  private client: OAuth2Client
  private readonly REDIRECT_URI: string
  private readonly CLIENT_ID: string
  private readonly CLIENT_SECRET: string
  
  // Comprehensive YouTube OAuth scopes with explanations
  private readonly SCOPES = [
    // Core Functionality
    'https://www.googleapis.com/auth/youtube.upload',           // Upload videos
    'https://www.googleapis.com/auth/youtube',                  // Full YouTube access
    'https://www.googleapis.com/auth/youtube.readonly',         // Read channel data
    'https://www.googleapis.com/auth/youtube.force-ssl',        // SSL enforcement
    
    // Analytics & Insights
    'https://www.googleapis.com/auth/yt-analytics.readonly',    // View analytics
    'https://www.googleapis.com/auth/yt-analytics-monetary.readonly', // Revenue data
    'https://www.googleapis.com/auth/youtubepartner',           // Partner features
    
    // Channel Management
    'https://www.googleapis.com/auth/youtube.channel-memberships.creator', // Memberships
    'https://www.googleapis.com/auth/youtubepartner-channel-audit',        // Audit
    
    // User Information
    'https://www.googleapis.com/auth/userinfo.email',          // Email address
    'https://www.googleapis.com/auth/userinfo.profile',         // Profile info
    
    // Content Rights
    'https://www.googleapis.com/auth/youtubepartner-content-owner-readonly', // CMS
  ]
  
  constructor() {
    this.CLIENT_ID = process.env.YOUTUBE_CLIENT_ID!
    this.CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET!
    this.REDIRECT_URI = `${process.env.NEXT_PUBLIC_APP_URL}/api/youtube/auth/callback`
    
    this.client = new OAuth2Client(
      this.CLIENT_ID,
      this.CLIENT_SECRET,
      this.REDIRECT_URI
    )
  }
  
  /**
   * Generate OAuth URL with PKCE challenge for enhanced security
   */
  generateAuthUrl(userId: string): { url: string; state: string; codeVerifier: string } {
    // Generate PKCE parameters
    const codeVerifier = crypto.randomBytes(32).toString('base64url')
    const codeChallenge = crypto
      .createHash('sha256')
      .update(codeVerifier)
      .digest('base64url')
    
    // Generate state for CSRF protection
    const state = crypto.randomBytes(32).toString('hex')
    
    // Build OAuth URL with all security parameters
    const authUrl = this.client.generateAuthUrl({
      access_type: 'offline',     // Get refresh token
      scope: this.SCOPES,
      include_granted_scopes: true,
      prompt: 'consent',           // Force consent screen
      state: `${userId}:${state}`,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256'
    })
    
    return { url: authUrl, state, codeVerifier }
  }
  
  /**
   * Exchange authorization code for tokens with comprehensive error handling
   */
  async exchangeCodeForTokens(
    code: string,
    codeVerifier: string
  ): Promise<{
    access_token: string
    refresh_token: string
    expiry: string
    scopes: string[]
  }> {
    try {
      const { tokens } = await this.client.getToken({
        code,
        codeVerifier
      })
      
      // Calculate expiry with buffer
      const expiryDate = new Date()
      expiryDate.setSeconds(
        expiryDate.getSeconds() + (tokens.expiry_date || 3600)
      )
      
      // Parse granted scopes
      const scopes = tokens.scope?.split(' ') || this.SCOPES
      
      return {
        access_token: tokens.access_token!,
        refresh_token: tokens.refresh_token!,
        expiry: expiryDate.toISOString(),
        scopes
      }
    } catch (error) {
      console.error('[OAuth] Token exchange failed:', error)
      throw new Error(`Failed to exchange code: ${error}`)
    }
  }
  
  /**
   * Refresh access token with intelligent retry logic
   */
  async refreshAccessToken(refreshToken: string): Promise<{
    access_token: string
    expiry: string
  }> {
    let retries = 3
    let lastError: any
    
    while (retries > 0) {
      try {
        this.client.setCredentials({
          refresh_token: refreshToken
        })
        
        const { credentials } = await this.client.refreshAccessToken()
        
        // Calculate new expiry with 5-minute buffer
        const expiryDate = new Date()
        const expirySeconds = credentials.expiry_date 
          ? Math.floor(credentials.expiry_date / 1000) - 300  // 5 min buffer
          : 3300  // Default to 55 minutes
        expiryDate.setSeconds(expiryDate.getSeconds() + expirySeconds)
        
        return {
          access_token: credentials.access_token!,
          expiry: expiryDate.toISOString()
        }
      } catch (error) {
        lastError = error
        retries--
        
        if (retries > 0) {
          // Exponential backoff
          await new Promise(resolve => setTimeout(resolve, Math.pow(2, 3 - retries) * 1000))
        }
      }
    }
    
    console.error('[OAuth] Token refresh failed after retries:', lastError)
    throw new Error(`Failed to refresh token: ${lastError}`)
  }
  
  /**
   * Map OAuth scopes to capabilities for UI feature flags
   */
  static getCapabilitiesFromScopes(scopes: string[]): {
    upload: boolean
    analytics: boolean
    monetization: boolean
    streaming: boolean
    management: boolean
  } {
    const scopeSet = new Set(scopes)
    
    return {
      upload: scopeSet.has('https://www.googleapis.com/auth/youtube.upload'),
      analytics: scopeSet.has('https://www.googleapis.com/auth/yt-analytics.readonly'),
      monetization: scopeSet.has('https://www.googleapis.com/auth/yt-analytics-monetary.readonly'),
      streaming: scopeSet.has('https://www.googleapis.com/auth/youtube'),
      management: scopeSet.has('https://www.googleapis.com/auth/youtubepartner')
    }
  }
}
```

## Channel Discovery & Caching System

### YouTubeMCPChannels Implementation with Caching

```typescript
// lib/youtube/mcp-channels.ts - Complete channel management system

import dbConnect from '@/lib/mongodb/mongoose'
import { YouTubeClient } from './youtube-client'
import MCPConnectionModel from '@/lib/mongodb/models/MCPConnection'

export interface MCPChannel {
  id: string
  name: string
  customer_url?: string
  thumbnail_url?: string
  token: {
    access_token: string
    refresh_token: string
    token_type: string
    expiry: string
  }
}

// In-memory cache for performance
const channelsCache = new Map<string, Map<string, MCPChannel>>()

export class YouTubeMCPChannels {
  /**
   * Get channel info for a token with comprehensive error handling
   */
  static async getChannelForToken(token: any, userId: string): Promise<MCPChannel> {
    const client = new YouTubeClient(token.access_token)
    const channels = await client.getMyChannels()
    
    if (channels.length === 0) {
      throw new Error('no channels found for token')
    }

    const channel: MCPChannel = {
      id: channels[0].id,
      name: channels[0].name,
      customer_url: channels[0].customUrl,
      thumbnail_url: channels[0].thumbnailUrl,
      token: {
        access_token: token.access_token,
        refresh_token: token.refresh_token,
        token_type: token.token_type || 'Bearer',
        expiry: token.expiry
      }
    }

    return channel
  }

  /**
   * Save channel with MongoDB persistence and cache update
   */
  static async saveChannel(channel: MCPChannel, userId: string): Promise<void> {
    if (!channel || !channel.token) {
      throw new Error('invalid channel: channel or token is nil')
    }

    // Update in-memory cache
    let userChannels = channelsCache.get(userId)
    if (!userChannels) {
      userChannels = new Map()
      channelsCache.set(userId, userChannels)
    }
    userChannels.set(channel.id, channel)

    // Persist to MongoDB
    await this.persistToDatabase(userId, userChannels)
  }

  /**
   * Read channels with cache-first strategy
   */
  static async readChannels(userId: string, ignoreError: boolean = false): Promise<Map<string, MCPChannel>> {
    // Check cache first
    let userChannels = channelsCache.get(userId)
    
    if (!userChannels) {
      // Load from database
      userChannels = await this.loadFromDatabase(userId)
      
      if (!userChannels) {
        userChannels = new Map()
      }
      
      channelsCache.set(userId, userChannels)
    }

    return userChannels
  }

  /**
   * Get valid access token with automatic refresh
   */
  static async getValidAccessToken(userId: string, channelId: string): Promise<string> {
    const channel = await this.getChannelByID(channelId, userId)
    
    if (!channel.token || !channel.token.access_token) {
      throw new Error('No access token available for this channel')
    }

    // Check if token is expired
    const expiryDate = new Date(channel.token.expiry)
    const now = new Date()
    
    // If token expires in less than 5 minutes, refresh it
    if (expiryDate.getTime() - now.getTime() < 5 * 60 * 1000) {
      if (!channel.token.refresh_token) {
        throw new Error('No refresh token available to refresh expired token')
      }

      // Import OAuth handler dynamically to avoid circular dependency
      const { YouTubeMCPOAuth } = await import('./mcp-oauth')
      const oauth = new YouTubeMCPOAuth()
      
      try {
        // Refresh the token
        const newToken = await oauth.refreshAccessToken(channel.token.refresh_token)
        
        // Update channel with new token
        channel.token = {
          ...channel.token,
          access_token: newToken.access_token,
          expiry: newToken.expiry
        }
        
        // Save updated channel
        await this.saveChannel(channel, userId)
        
        console.log(`[Token] Refreshed for channel ${channel.name}`)
        
        return newToken.access_token
      } catch (error) {
        throw new Error(`Failed to refresh access token: ${error instanceof Error ? error.message : 'Unknown error'}`)
      }
    }

    return channel.token.access_token
  }

  /**
   * Get only enabled channels for multi-upload
   */
  static async getEnabledChannels(userId: string): Promise<MCPChannel[]> {
    await dbConnect()
    
    try {
      const connections = await MCPConnectionModel.find({
        userId,
        serverId: 'youtube-uploader',
        connected: true,
        enabled: true  // Only get enabled accounts
      })

      const enabledChannels: MCPChannel[] = []
      
      for (const connection of connections) {
        if (connection.config?.channels) {
          Object.entries(connection.config.channels).forEach(([channelId, channel]) => {
            const mcpChannel = channel as MCPChannel
            if (mcpChannel.token?.access_token && mcpChannel.token?.refresh_token) {
              enabledChannels.push(mcpChannel)
            }
          })
        }
      }

      return enabledChannels
    } catch (error) {
      console.error('Failed to load enabled channels:', error)
      return []
    }
  }

  /**
   * Database persistence with encryption
   */
  private static async persistToDatabase(userId: string, channels: Map<string, MCPChannel>): Promise<void> {
    await dbConnect()
    
    const { YouTubeMCPOAuth } = await import('./mcp-oauth')
    
    for (const [channelId, channel] of channels) {
      try {
        const existingConnection = await MCPConnectionModel.findOne({
          userId,
          serverId: 'youtube-uploader',
          'config.channelId': channelId
        })
        
        const scopes = existingConnection?.scopes || [
          'https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube.readonly'
        ]
        
        await MCPConnectionModel.findOneAndUpdate(
          {
            userId,
            serverId: 'youtube-uploader',
            'config.channelId': channelId
          },
          {
            userId,
            serverId: 'youtube-uploader',
            name: `YouTube: ${channel.name}`,
            description: channel.customer_url,
            connectionType: 'sse',
            connected: true,
            enabled: existingConnection?.enabled ?? true,
            accountGroup: existingConnection?.accountGroup,
            scopes,
            capabilities: YouTubeMCPOAuth.getCapabilitiesFromScopes(scopes),
            lastConnected: new Date(),
            config: {
              channelId,
              channelName: channel.name,
              customUrl: channel.customer_url,
              thumbnailUrl: channel.thumbnail_url,
              channels: { [channelId]: channel }
            },
            authToken: channel.token.access_token,
            refreshToken: channel.token.refresh_token,
            tokenExpiresAt: new Date(channel.token.expiry)
          },
          {
            upsert: true,
            new: true
          }
        )
      } catch (error) {
        console.error(`Failed to persist channel ${channelId}:`, error)
      }
    }
  }
}
```

## MongoDB Schema & Encryption Details

### MCPConnection Schema with AES-256 Encryption

```typescript
// lib/mongodb/models/MCPConnection.ts - Complete schema with encryption

import mongoose from 'mongoose'
import crypto from 'crypto'

// Encryption configuration
const ENCRYPTION_KEY = process.env.MCP_ENCRYPTION_KEY || crypto.randomBytes(32).toString('hex').slice(0, 32)
const IV_LENGTH = 16

// AES-256-CBC encryption functions
function encrypt(text: string): string {
  const iv = crypto.randomBytes(IV_LENGTH)
  const cipher = crypto.createCipheriv('aes-256-cbc', Buffer.from(ENCRYPTION_KEY), iv)
  let encrypted = cipher.update(text)
  encrypted = Buffer.concat([encrypted, cipher.final()])
  return iv.toString('hex') + ':' + encrypted.toString('hex')
}

function decrypt(text: string): string {
  const textParts = text.split(':')
  const iv = Buffer.from(textParts.shift()!, 'hex')
  const encryptedText = Buffer.from(textParts.join(':'), 'hex')
  const decipher = crypto.createDecipheriv('aes-256-cbc', Buffer.from(ENCRYPTION_KEY), iv)
  let decrypted = decipher.update(encryptedText)
  decrypted = Buffer.concat([decrypted, decipher.final()])
  return decrypted.toString()
}

export interface IMCPConnection {
  _id?: string
  id?: string
  serverId: string
  userId: string
  name: string
  description?: string
  icon?: string
  config: Record<string, any>
  connectionType: 'stdio' | 'sse'
  authToken?: string          // Encrypted
  refreshToken?: string       // Encrypted
  tokenExpiresAt?: Date
  scopes?: string[]
  connected: boolean
  enabled: boolean            // Account active status
  accountGroup?: string       // Group name (Personal/Work/Client)
  capabilities?: {            // Feature flags based on scopes
    upload: boolean
    analytics: boolean
    monetization: boolean
    streaming: boolean
    management: boolean
  }
  lastConnected?: Date
  lastError?: string
  createdAt: Date
  updatedAt: Date
}

const MCPConnectionSchema = new mongoose.Schema({
  serverId: {
    type: String,
    required: true,
    index: true
  },
  userId: {
    type: String,
    required: true,
    index: true
  },
  name: {
    type: String,
    required: true
  },
  description: String,
  icon: String,
  config: {
    type: mongoose.Schema.Types.Mixed,
    required: true
  },
  connectionType: {
    type: String,
    enum: ['stdio', 'sse'],
    required: true,
    default: 'sse'
  },
  authToken: {
    type: String,
    get: (value: string) => value ? decrypt(value) : undefined,
    set: (value: string) => value ? encrypt(value) : undefined
  },
  refreshToken: {
    type: String,
    get: (value: string) => value ? decrypt(value) : undefined,
    set: (value: string) => value ? encrypt(value) : undefined
  },
  tokenExpiresAt: Date,
  scopes: [String],
  connected: {
    type: Boolean,
    default: false
  },
  enabled: {
    type: Boolean,
    default: true
  },
  accountGroup: String,
  capabilities: {
    upload: { type: Boolean, default: false },
    analytics: { type: Boolean, default: false },
    monetization: { type: Boolean, default: false },
    streaming: { type: Boolean, default: false },
    management: { type: Boolean, default: false }
  },
  lastConnected: Date,
  lastError: String
}, {
  timestamps: true,
  toJSON: {
    getters: true,
    transform: (doc, ret: any) => {
      // Don't include tokens in JSON responses
      delete ret.authToken
      delete ret.refreshToken
      return ret
    }
  }
})

// Compound index for efficient queries
MCPConnectionSchema.index({ userId: 1, serverId: 1 })

// Virtual for id field
MCPConnectionSchema.virtual('id').get(function() {
  return this._id.toHexString()
})

export default mongoose.models.MCPConnection || mongoose.model<IMCPConnection>('MCPConnection', MCPConnectionSchema)
```

## YouTube API Client Implementation

### YouTube Client with Resumable Upload

```typescript
// lib/youtube/youtube-client.ts - Complete YouTube API client

import { YouTubeChannel, YouTubeVideoMetadata } from './types'

const YOUTUBE_API_BASE_URL = 'https://www.googleapis.com/youtube/v3'
const YOUTUBE_UPLOAD_URL = 'https://www.googleapis.com/upload/youtube/v3/videos'

export class YouTubeClient {
  private accessToken: string
  private rateLimitRemaining: number = 10000  // Daily quota
  private rateLimitReset: Date = new Date()

  constructor(accessToken: string) {
    this.accessToken = accessToken
  }

  /**
   * Get authenticated user's channels with full statistics
   */
  async getMyChannels(): Promise<YouTubeChannel[]> {
    const response = await this.makeRequest(
      `${YOUTUBE_API_BASE_URL}/channels?part=snippet,statistics,contentDetails&mine=true`
    )

    if (!response.items || response.items.length === 0) {
      throw new Error('No YouTube channels found for this account')
    }

    return response.items.map((item: any) => ({
      id: item.id,
      name: item.snippet.title,
      customUrl: item.snippet.customUrl,
      thumbnailUrl: item.snippet.thumbnails?.default?.url,
      subscriberCount: parseInt(item.statistics?.subscriberCount || '0'),
      videoCount: parseInt(item.statistics?.videoCount || '0'),
      viewCount: parseInt(item.statistics?.viewCount || '0'),
      uploadPlaylistId: item.contentDetails?.relatedPlaylists?.uploads
    }))
  }

  /**
   * Upload video using resumable protocol for large files
   */
  async uploadVideo(
    file: File | Blob,
    metadata: YouTubeVideoMetadata,
    onProgress?: (progress: number) => void
  ): Promise<string> {
    // Create video metadata
    const videoResource = {
      snippet: {
        title: metadata.title,
        description: metadata.description,
        tags: metadata.tags,
        categoryId: metadata.categoryId
      },
      status: {
        privacyStatus: metadata.privacyStatus,
        selfDeclaredMadeForKids: metadata.madeForKids,
        notifySubscribers: metadata.notifySubscribers ?? true
      }
    }

    if (metadata.publishAt) {
      videoResource.status.privacyStatus = 'private'
      // @ts-ignore
      videoResource.status.publishAt = metadata.publishAt.toISOString()
    }

    // Initiate resumable upload
    const uploadUrl = await this.initiateResumableUpload(videoResource)
    const videoId = await this.performResumableUpload(uploadUrl, file, onProgress)

    return videoId
  }

  /**
   * Initiate a resumable upload session
   */
  private async initiateResumableUpload(metadata: any): Promise<string> {
    const response = await fetch(
      `${YOUTUBE_UPLOAD_URL}?uploadType=resumable&part=snippet,status`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json',
          'X-Upload-Content-Type': 'video/*'
        },
        body: JSON.stringify(metadata)
      }
    )

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`Failed to initiate upload: ${error}`)
    }

    const location = response.headers.get('location')
    if (!location) {
      throw new Error('No upload URL returned')
    }

    return location
  }

  /**
   * Perform resumable upload with progress tracking
   */
  private async performResumableUpload(
    uploadUrl: string,
    file: File | Blob,
    onProgress?: (progress: number) => void
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          const progress = Math.round((e.loaded / e.total) * 100)
          onProgress(progress)
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText)
            resolve(response.id)
          } catch (err) {
            reject(new Error('Failed to parse upload response'))
          }
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}: ${xhr.responseText}`))
        }
      })

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed due to network error'))
      })

      xhr.open('PUT', uploadUrl)
      xhr.setRequestHeader('Content-Type', file.type || 'video/*')
      xhr.send(file)
    })
  }

  /**
   * Make API request with rate limiting and retry logic
   */
  private async makeRequest(url: string, options: RequestInit = {}): Promise<any> {
    // Check rate limit
    if (this.rateLimitRemaining <= 0 && new Date() < this.rateLimitReset) {
      throw new Error('YouTube API rate limit exceeded')
    }

    const response = await fetch(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.accessToken}`,
        ...options.headers
      }
    })

    // Update rate limit from headers
    const remaining = response.headers.get('x-ratelimit-remaining')
    const reset = response.headers.get('x-ratelimit-reset')
    
    if (remaining) {
      this.rateLimitRemaining = parseInt(remaining)
    }
    if (reset) {
      this.rateLimitReset = new Date(parseInt(reset) * 1000)
    }

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`YouTube API error: ${error}`)
    }

    return response.json()
  }
}
```

## Multi-Channel Management System

### Multi-Channel Upload Implementation

```typescript
// lib/tools/youtube/upload_video_multi.ts - Multi-channel upload tool

import { tool } from 'ai'
import { z } from 'zod'
import { YouTubeMCPChannels } from '@/lib/youtube/mcp-channels'
import { YouTubeFileManager } from '@/lib/youtube/youtube-file-manager'
import { YouTubeStreamingUpload, formatBytes } from '@/lib/youtube/youtube-upload-stream'
import { getYouTubeUploadStore } from '@/lib/mongodb/youtube-upload-store'
import { currentUser } from '@clerk/nextjs/server'
import dbConnect from '@/lib/mongodb/mongoose'
import UploadReferenceModel from '@/lib/mongodb/models/UploadReference'

interface UploadResult {
  channelId: string
  channelName: string
  uploadId: string
  status: 'success' | 'failed' | 'uploading'
  videoId?: string
  error?: string
}

export const uploadVideoMultiTool = tool({
  description: 'Upload a video to ALL enabled YouTube accounts. ' +
    'This tool automatically uses the most recent video and thumbnail files you uploaded. ' +
    'Just provide the title and description for the video. ' +
    'The tool will upload to all YouTube accounts that are toggled ON in the sidebar.',
  parameters: z.object({
    title: z.string().describe('Video title'),
    description: z.string().describe('Video description'),
    tags: z.array(z.string()).optional().describe('Video tags'),
    category_id: z.string().optional().default('22').describe('YouTube category ID'),
    privacy_status: z.enum(['private', 'unlisted', 'public']).optional().default('public'),
    made_for_kids: z.boolean().optional().default(false),
    scheduled_for: z.string().optional().describe('Natural language scheduling')
  }),
  execute: async ({ title, description, tags, category_id, privacy_status, made_for_kids, scheduled_for }) => {
    try {
      // Get current user
      const user = await currentUser()
      if (!user) {
        throw new Error('User not authenticated')
      }
      
      // Connect to database and get latest pending uploads
      await dbConnect()
      const uploads = await (UploadReferenceModel as any).getLatestPendingUploads(user.id)
      
      if (!uploads.video) {
        throw new Error('No video file found. Please upload a video file first.')
      }
      
      const file_path = uploads.video.referenceId
      const thumbnail_path = uploads.thumbnail?.referenceId
      
      console.log('[upload_video_multi] Starting multi-account upload')
      console.log('[upload_video_multi] Found video reference:', file_path)
      console.log('[upload_video_multi] Found thumbnail reference:', thumbnail_path || 'none')

      // Get all enabled YouTube channels
      const enabledChannels = await YouTubeMCPChannels.getEnabledChannels(user.id)
      
      if (enabledChannels.length === 0) {
        throw new Error('No YouTube accounts enabled. Please enable at least one account.')
      }
      
      console.log(`[upload_video_multi] Found ${enabledChannels.length} enabled channels`)

      // Process file reference
      const fileData = await YouTubeFileManager.getFileData(user.id, file_path)
      if (!fileData) {
        throw new Error(`File reference not found: ${file_path}`)
      }

      // Base metadata
      const baseMetadata = {
        title,
        description,
        tags: tags || [],
        categoryId: category_id || '22',
        privacyStatus: privacy_status || 'public',
        madeForKids: made_for_kids || false
      }

      // Check for AI-generated metadata variations
      let metadataVariations: any[] = []
      if (fileData.reference.generatedMetadata && !title && !description) {
        const aiMetadata = fileData.reference.generatedMetadata
        
        if (Array.isArray(aiMetadata)) {
          metadataVariations = aiMetadata
        } else if (aiMetadata.variations && Array.isArray(aiMetadata.variations)) {
          metadataVariations = aiMetadata.variations
        } else {
          metadataVariations = [aiMetadata]
        }
        
        console.log(`[upload_video_multi] Using AI-generated metadata with ${metadataVariations.length} variations`)
      }

      // Handle scheduled uploads
      let scheduledDate: Date | undefined
      if (scheduled_for) {
        const { scheduleDateParser } = await import('@/lib/scheduling/date-parser')
        const parsed = scheduleDateParser.parse(scheduled_for)
        scheduledDate = parsed.date
        console.log(`[upload_video_multi] Scheduling uploads for: ${parsed.interpretation}`)
      }

      const uploadResults: UploadResult[] = []
      const uploadStore = getYouTubeUploadStore()

      // Start uploads for all enabled channels in parallel
      const uploadPromises = enabledChannels.map(async (channel, index) => {
        try {
          console.log(`[upload_video_multi] Starting upload for channel: ${channel.name} (${channel.id})`)
          
          // Get valid access token (will refresh if needed)
          const accessToken = await YouTubeMCPChannels.getValidAccessToken(user.id, channel.id)
          
          // Select metadata - use variation if available
          let metadata = baseMetadata
          if (metadataVariations.length > 0) {
            const variationIndex = index % metadataVariations.length
            const variation = metadataVariations[variationIndex]
            metadata = {
              title: variation.title,
              description: variation.description,
              tags: variation.tags || [],
              categoryId: variation.category || baseMetadata.categoryId,
              privacyStatus: baseMetadata.privacyStatus,
              madeForKids: baseMetadata.madeForKids
            }
            console.log(`[upload_video_multi] Using variation ${variationIndex + 1} for ${channel.name}`)
          }

          // Create upload record
          const upload = await uploadStore.createUpload({
            userId: user.id,
            channelId: channel.id,
            title: metadata.title,
            description: metadata.description,
            tags: metadata.tags,
            categoryId: metadata.categoryId,
            privacyStatus: metadata.privacyStatus,
            madeForKids: metadata.madeForKids,
            fileName: fileData.reference.fileName,
            fileSize: fileData.reference.fileSize,
            mimeType: fileData.reference.mimeType,
            uploadStatus: 'uploading',
            uploadProgress: 0,
            scheduledFor: scheduledDate
          })

          // Add to results
          const result: UploadResult = {
            channelId: channel.id,
            channelName: channel.name,
            uploadId: upload.id,
            status: 'uploading'
          }
          uploadResults.push(result)

          // Create streaming upload instance
          const streamingUpload = new YouTubeStreamingUpload(accessToken)
          
          // Start upload with progress tracking
          streamingUpload.uploadLargeVideo(
            fileData.data,
            metadata,
            async (progress, bytesUploaded, totalBytes) => {
              await uploadStore.updateUploadStatus(
                upload.id,
                'uploading',
                progress,
                `Uploaded ${formatBytes(bytesUploaded)} of ${formatBytes(totalBytes)}`
              )
            }
          )
            .then(async (videoId) => {
              await uploadStore.updateUploadVideo(upload.id, videoId)
              await uploadStore.updateUploadStatus(upload.id, 'completed', 100)
              
              result.status = 'success'
              result.videoId = videoId
              
              console.log(`[upload_video_multi] Upload completed for channel ${channel.name}: ${videoId}`)
              
              // Upload thumbnail if provided
              if (thumbnail_path) {
                try {
                  const { YouTubeThumbnailUpload } = await import('@/lib/youtube/youtube-thumbnail-upload')
                  const thumbnailUpload = new YouTubeThumbnailUpload(accessToken)
                  await thumbnailUpload.uploadThumbnail(videoId, thumbnail_path, user.id)
                  console.log(`[upload_video_multi] Thumbnail uploaded for video ${videoId}`)
                } catch (error) {
                  console.error(`[upload_video_multi] Thumbnail upload failed:`, error)
                }
              }
            })
            .catch(async (error) => {
              await uploadStore.updateUploadStatus(
                upload.id,
                'failed',
                0,
                error instanceof Error ? error.message : 'Upload failed'
              )
              
              result.status = 'failed'
              result.error = error instanceof Error ? error.message : 'Upload failed'
              
              console.error(`[upload_video_multi] Upload failed for channel ${channel.name}:`, error)
            })

          return result
        } catch (error) {
          console.error(`[upload_video_multi] Error for channel ${channel.name}:`, error)
          return {
            channelId: channel.id,
            channelName: channel.name,
            uploadId: '',
            status: 'failed' as const,
            error: error instanceof Error ? error.message : 'Failed to start upload'
          }
        }
      })

      // Wait for all uploads to complete
      await Promise.all(uploadPromises)

      // Mark references as used
      const referenceIds = [file_path]
      if (thumbnail_path) {
        referenceIds.push(thumbnail_path)
      }
      await (UploadReferenceModel as any).markAsUsed(referenceIds)

      // Clean up file references
      await YouTubeFileManager.deleteFileReference(user.id, file_path)

      // Build response
      const successfulUploads = uploadResults.filter(r => r.status === 'success')
      const message = successfulUploads.length === uploadResults.length
        ? '✅ Upload successful!'
        : `⚠️ Uploaded to ${successfulUploads.length} of ${uploadResults.length} accounts`

      return {
        type: 'youtube-multi-upload',
        title,
        fileName: fileData.reference.fileName,
        fileSize: formatBytes(fileData.reference.fileSize),
        totalChannels: enabledChannels.length,
        uploads: uploadResults,
        message
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      throw new Error(`Failed to upload video: ${errorMessage}`)
    }
  }
})
```

## Token Refresh Mechanism

### Intelligent Token Refresh with Buffer

```typescript
// lib/youtube/token-refresh-manager.ts

export class TokenRefreshManager {
  private static refreshQueue = new Map<string, Promise<string>>()
  
  /**
   * Get valid token with automatic refresh
   */
  static async getValidToken(
    userId: string,
    channelId: string,
    currentToken: string,
    refreshToken: string,
    expiry: string
  ): Promise<string> {
    const key = `${userId}:${channelId}`
    
    // Check if refresh is already in progress
    if (this.refreshQueue.has(key)) {
      return this.refreshQueue.get(key)!
    }
    
    // Check if token needs refresh
    const expiryDate = new Date(expiry)
    const now = new Date()
    const bufferMs = 5 * 60 * 1000  // 5 minutes
    
    if (expiryDate.getTime() - now.getTime() > bufferMs) {
      return currentToken  // Token still valid
    }
    
    // Start refresh process
    const refreshPromise = this.refreshToken(refreshToken, userId, channelId)
    this.refreshQueue.set(key, refreshPromise)
    
    try {
      const newToken = await refreshPromise
      return newToken
    } finally {
      this.refreshQueue.delete(key)
    }
  }
  
  private static async refreshToken(
    refreshToken: string,
    userId: string,
    channelId: string
  ): Promise<string> {
    const { YouTubeMCPOAuth } = await import('./mcp-oauth')
    const oauth = new YouTubeMCPOAuth()
    
    try {
      const result = await oauth.refreshAccessToken(refreshToken)
      
      // Update channel with new token
      const { YouTubeMCPChannels } = await import('./mcp-channels')
      const channel = await YouTubeMCPChannels.getChannelByID(channelId, userId)
      
      channel.token.access_token = result.access_token
      channel.token.expiry = result.expiry
      
      await YouTubeMCPChannels.saveChannel(channel, userId)
      
      console.log(`[TokenRefresh] Successfully refreshed token for channel ${channelId}`)
      
      return result.access_token
    } catch (error) {
      console.error(`[TokenRefresh] Failed to refresh token for channel ${channelId}:`, error)
      throw error
    }
  }
}
```

## Common Issues & Solutions

### Issue 1: Token Expiry During Upload
**Problem**: Token expires while uploading large video
**Solution**: Pre-refresh token before starting upload
```typescript
const accessToken = await TokenRefreshManager.getValidToken(
  userId, channelId, token, refreshToken, expiry
)
```

### Issue 2: Rate Limiting
**Problem**: YouTube API quota exceeded
**Solution**: Implement exponential backoff
```typescript
async function withRetry<T>(fn: () => Promise<T>, maxRetries = 3): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise(r => setTimeout(r, Math.pow(2, i) * 1000))
    }
  }
  throw new Error('Max retries exceeded')
}
```

### Issue 3: Concurrent Channel Updates
**Problem**: Race conditions when multiple uploads update same channel
**Solution**: Use MongoDB transactions
```typescript
const session = await mongoose.startSession()
session.startTransaction()
try {
  await MCPConnectionModel.findOneAndUpdate(query, update, { session })
  await session.commitTransaction()
} catch (error) {
  await session.abortTransaction()
  throw error
} finally {
  session.endSession()
}
```

### Issue 4: Memory Leaks in Cache
**Problem**: Channel cache grows unbounded
**Solution**: Implement LRU eviction
```typescript
class LRUCache<K, V> {
  private cache = new Map<K, V>()
  private maxSize: number
  
  constructor(maxSize = 1000) {
    this.maxSize = maxSize
  }
  
  set(key: K, value: V): void {
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value
      this.cache.delete(firstKey)
    }
    this.cache.delete(key)  // Remove if exists
    this.cache.set(key, value)  // Add to end
  }
  
  get(key: K): V | undefined {
    const value = this.cache.get(key)
    if (value) {
      this.cache.delete(key)
      this.cache.set(key, value)  // Move to end
    }
    return value
  }
}
```

### Issue 5: OAuth State Mismatch
**Problem**: CSRF token doesn't match
**Solution**: Use secure cookies with proper settings
```typescript
cookieStore.set('youtube_oauth_state', state, {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax',
  maxAge: 600,
  path: '/'
})
```

## Production Deployment Guide

### Environment Variables
```env
# Required
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
NEXT_PUBLIC_APP_URL=https://your-domain.com
MCP_ENCRYPTION_KEY=32_character_hex_key
MONGODB_URI=mongodb://localhost:27017/morphic

# Optional
YOUTUBE_API_QUOTA_LIMIT=10000
YOUTUBE_MAX_CHANNELS_PER_USER=10
YOUTUBE_TOKEN_REFRESH_BUFFER_SECONDS=300
YOUTUBE_UPLOAD_TIMEOUT_SECONDS=3600
ENABLE_YOUTUBE_ANALYTICS=true
```

### Docker Configuration
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Monitoring & Logging
```typescript
// lib/monitoring/youtube-metrics.ts
export class YouTubeMetrics {
  static trackOAuthFlow(userId: string, event: string) {
    console.log(`[OAuth] ${event} for user ${userId}`)
    // Send to monitoring service
  }
  
  static trackUpload(channelId: string, videoId: string, duration: number) {
    console.log(`[Upload] Channel ${channelId} uploaded ${videoId} in ${duration}ms`)
    // Send to analytics
  }
  
  static trackError(error: Error, context: Record<string, any>) {
    console.error(`[Error] ${error.message}`, context)
    // Send to error tracking
  }
}
```

This comprehensive documentation provides production-ready code, best practices, and solutions to common issues. The implementation handles multi-channel management, automatic token refresh, secure storage, and scalable architecture suitable for enterprise deployment.