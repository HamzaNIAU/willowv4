import React, { type ElementType } from 'react';
import {
  FileText,
  Terminal,
  ExternalLink,
  FileEdit,
  Search,
  Globe,
  Code,
  MessageSquare,
  Folder,
  FileX,
  CloudUpload,
  Wrench,
  Cog,
  Network,
  FileSearch,
  FilePlus,
  PlugIcon,
  BookOpen,
  MessageCircleQuestion,
  CheckCircle2,
  Table2,
  ListTodo,
  List,
} from 'lucide-react';

// Custom platform icon components using static assets
const YouTubeIcon: ElementType = (props: any) => 
  React.createElement('img', {
    src: '/platforms/youtube.svg',
    alt: 'YouTube',
    className: props.className || 'h-4 w-4',
    ...props
  });

// Pinterest icon rendered within a rounded container so it doesn't appear as a red square
const PinterestIcon: ElementType = (props: any) => {
  const { className, ...rest } = props || {};
  return (
    <span className={className} {...rest}>
      <img
        src="/platforms/pinterest.png"
        alt="Pinterest"
        className="h-full w-full rounded-full"
      />
    </span>
  );
};

const InstagramIcon: ElementType = (props: any) =>
  React.createElement('img', {
    src: '/platforms/instagram.png',
    alt: 'Instagram',
    className: props.className || 'h-4 w-4',
    ...props
  });

const TwitterXIcon: ElementType = (props: any) =>
  React.createElement('img', {
    src: '/platforms/x.png',
    alt: 'X',
    className: props.className || 'h-4 w-4',
    ...props
  });

const LinkedInIcon: ElementType = (props: any) =>
  React.createElement('img', {
    src: '/platforms/linkedin.png',
    alt: 'LinkedIn',
    className: props.className || 'h-4 w-4',
    ...props
  });

const TikTokIcon: ElementType = (props: any) =>
  React.createElement('img', {
    src: '/platforms/tiktok.png',
    alt: 'TikTok',
    className: props.className || 'h-4 w-4',
    ...props
  });

// Flag to control whether tool result messages are rendered
export const SHOULD_RENDER_TOOL_RESULTS = false;

// Helper function to safely parse JSON strings from content/metadata
export function safeJsonParse<T>(
  jsonString: string | undefined | null,
  fallback: T,
): T {
  if (!jsonString) {
    return fallback;
  }
  
  try {
    // First attempt: Parse as normal JSON
    const parsed = JSON.parse(jsonString);
    
    // Check if the result is a string that looks like JSON (double-escaped case)
    if (typeof parsed === 'string' && 
        (parsed.startsWith('{') || parsed.startsWith('['))) {
      try {
        // Second attempt: Parse the string result as JSON (handles double-escaped)
        return JSON.parse(parsed) as T;
      } catch (innerError) {
        // If inner parse fails, return the first parse result
        return parsed as unknown as T;
      }
    }
    
    return parsed as T;
  } catch (outerError) {
    // If the input is already an object/array (shouldn't happen but just in case)
    if (typeof jsonString === 'object') {
      return jsonString as T;
    }
    
    // Try one more time in case it's a plain string that should be returned as-is
    if (typeof jsonString === 'string') {
      // Check if it's a string representation of a simple value
      if (jsonString === 'true') return true as unknown as T;
      if (jsonString === 'false') return false as unknown as T;
      if (jsonString === 'null') return null as unknown as T;
      if (!isNaN(Number(jsonString))) return Number(jsonString) as unknown as T;
      
      // Return as string if it doesn't look like JSON
      if (!jsonString.startsWith('{') && !jsonString.startsWith('[')) {
        return jsonString as unknown as T;
      }
    }
    
    // console.warn('Failed to parse JSON string:', jsonString, outerError); // Optional: log errors
    return fallback;
  }
}

// Helper function to get an icon based on tool name
export const getToolIcon = (toolName: string): ElementType => {
  switch (toolName?.toLowerCase()) {
    case 'browser-navigate-to':
    case 'browser-act':
    case 'browser-extract-content':
    case 'browser-screenshot':
      return Globe;

    // File operations
    case 'create-file':
      return FileEdit;
    case 'str-replace':
      return FileSearch;
    case 'full-file-rewrite':
      return FilePlus;
    case 'read-file':
      return FileText;
    case 'edit-file':
      return FileEdit;

    // Task operations
    case 'create-tasks':
      return List;
    case 'update-tasks':
      return ListTodo;

    // Shell commands
    case 'execute-command':
      return Terminal;
    case 'check-command-output':
      return Terminal;
    case 'terminate-command':
      return Terminal;

    // Web operations
    case 'web-search':
      return Search;
    case 'crawl-webpage':
      return Globe;
    case 'scrape-webpage':
        return Globe;

    // API and data operations
    case 'call-data-provider':
      return ExternalLink;
    case 'get-data-provider-endpoints':
      return Network;
    case 'execute-data-provider-call':
      return Network;

    // Sheets tools
    case 'create-sheet':
    case 'update-sheet':
    case 'view-sheet':
    case 'analyze-sheet':
    case 'visualize-sheet':
    case 'format-sheet':
      return Table2;

    // Code operations
    case 'delete-file':
      return FileX;

    // Deployment
    case 'deploy-site':
      return CloudUpload;

    // Tools and utilities
    case 'execute-code':
      return Code;

    // User interaction
    case 'ask':
      return MessageCircleQuestion;

    // Task completion
    case 'complete':
      return CheckCircle2;

    // YouTube tools
    case 'youtube-channels':
    case 'youtube-authenticate':
    case 'youtube-upload-video':
    case 'youtube-list-channel-videos':
    case 'youtube-manage-video':
    case 'youtube-list-captions':
    case 'youtube-download-caption':
    case 'youtube-list-playlists':
    case 'youtube-smart-search':
    case 'youtube-check-upload-status':
      return YouTubeIcon;

    // Pinterest
    case 'pinterest-authenticate':
    case 'pinterest-accounts':
    case 'pinterest-create-pin':
    case 'pinterest-pin-status':
    case 'pinterest-account-boards':
    case 'pinterest-recent-pins':
    case 'pinterest_authenticate':
    case 'pinterest_accounts':
    case 'pinterest_create_pin':
    case 'pinterest_pin_status':
    case 'pinterest_account_boards':
    case 'pinterest_recent_pins':
      return PinterestIcon;

    // Instagram
    case 'instagram-authenticate':
    case 'instagram-accounts':
    case 'instagram-create-post':
    case 'instagram-create-story':
    case 'instagram-get-posts':
    case 'instagram_authenticate':
    case 'instagram_accounts':
    case 'instagram_create_post':
    case 'instagram_create_story':
    case 'instagram_get_posts':
      return InstagramIcon;

    // Twitter / X
    case 'twitter-authenticate':
    case 'twitter-accounts':
    case 'twitter-create-tweet':
    case 'twitter-check-tweet-status':
    case 'twitter-search-tweets':
    case 'twitter_authenticate':
    case 'twitter_accounts':
    case 'twitter_create_tweet':
    case 'twitter_check_tweet_status':
    case 'twitter_search_tweets':
      return TwitterXIcon;

    // LinkedIn
    case 'linkedin-authenticate':
    case 'linkedin-accounts':
    case 'linkedin-create-post':
    case 'linkedin-post-status':
    case 'linkedin-account-posts':
    case 'linkedin_authenticate':
    case 'linkedin_accounts':
    case 'linkedin_create_post':
    case 'linkedin_post_status':
    case 'linkedin_account_posts':
      return LinkedInIcon;

    // TikTok
    case 'tiktok-authenticate':
    case 'tiktok-accounts':
    case 'tiktok-upload-video':
    case 'tiktok_authenticate':
    case 'tiktok_accounts':
    case 'tiktok_upload_video':
      return TikTokIcon;

    default:
      if (toolName?.startsWith('mcp_')) {
        const parts = toolName.split('_');
        if (parts.length >= 3) {
          const serverName = parts[1];
          const toolNamePart = parts.slice(2).join('_');
          
          // Map specific MCP tools to appropriate icons
          if (toolNamePart.includes('search') || toolNamePart.includes('web')) {
            return Search;
          } else if (toolNamePart.includes('research') || toolNamePart.includes('paper')) {
            return BookOpen;
          } else if (serverName === 'exa') {
            return Search; // Exa is primarily a search service
          }
        }
        return PlugIcon; // Default icon for MCP tools
      }
      
      // Add logging for debugging unhandled tool types
      return Wrench; // Default icon for tools
  }
};

// Map tool name to brand styles for chips/badges
export const getBrandStyles = (toolName: string): { bg: string; text: string } | null => {
  const t = toolName?.toLowerCase() || '';
  if (t.startsWith('youtube')) return { bg: 'bg-red-600', text: 'text-white' };
  if (t.startsWith('pinterest')) return { bg: 'bg-[#E60023]', text: 'text-white' };
  if (t.startsWith('instagram')) return { bg: 'bg-gradient-to-r from-purple-500 to-pink-500', text: 'text-white' };
  if (t.startsWith('twitter')) return { bg: 'bg-black', text: 'text-white' };
  if (t.startsWith('linkedin')) return { bg: 'bg-[#0A66C2]', text: 'text-white' };
  if (t.startsWith('tiktok')) return { bg: 'bg-black', text: 'text-white' };
  return null;
};

// Helper function to extract a primary parameter from XML/arguments
export const extractPrimaryParam = (
  toolName: string,
  content: string | undefined,
): string | null => {
  if (!content) return null;

  try {
    // Handle browser tools with a prefix check
    if (toolName?.toLowerCase().startsWith('browser_')) {
      // Try to extract URL for navigation
      const urlMatch = content.match(/url=(?:"|')([^"|']+)(?:"|')/);
      if (urlMatch) return urlMatch[1];

      // For other browser operations, extract the goal or action
      const goalMatch = content.match(/goal=(?:"|')([^"|']+)(?:"|')/);
      if (goalMatch) {
        const goal = goalMatch[1];
        return goal.length > 30 ? goal.substring(0, 27) + '...' : goal;
      }

      return null;
    }

    // Special handling for XML content - extract file_path from the actual attributes
    if (content.startsWith('<') && content.includes('>')) {
      const xmlAttrs = content.match(/<[^>]+\s+([^>]+)>/);
      if (xmlAttrs && xmlAttrs[1]) {
        const attrs = xmlAttrs[1].trim();
        const filePathMatch = attrs.match(/file_path=["']([^"']+)["']/);
        if (filePathMatch) {
          return filePathMatch[1].split('/').pop() || filePathMatch[1];
        }

        // Try to get command for execute-command
        if (toolName?.toLowerCase() === 'execute-command') {
          const commandMatch = attrs.match(/(?:command|cmd)=["']([^"']+)["']/);
          if (commandMatch) {
            const cmd = commandMatch[1];
            return cmd.length > 30 ? cmd.substring(0, 27) + '...' : cmd;
          }
        }
      }
    }

    // Simple regex for common parameters - adjust as needed
    let match: RegExpMatchArray | null = null;

    switch (toolName?.toLowerCase()) {
      // File operations
      case 'create-file':
      case 'full-file-rewrite':
      case 'read-file':
      case 'delete-file':
      case 'str-replace':
        // Try to match file_path attribute
        match = content.match(/file_path=(?:"|')([^"|']+)(?:"|')/);
        // Return just the filename part
        return match ? match[1].split('/').pop() || match[1] : null;
      case 'edit-file':
        // Try to match target_file attribute for edit-file
        match = content.match(/target_file=(?:"|')([^"|']+)(?:"|')/) || content.match(/<parameter\s+name=["']target_file["']>([^<]+)/i);
        // Return just the filename part
        return match ? (match[1].split('/').pop() || match[1]).trim() : null;

      // Shell commands
      case 'execute-command':
        // Extract command content
        match = content.match(/command=(?:"|')([^"|']+)(?:"|')/);
        if (match) {
          const cmd = match[1];
          return cmd.length > 30 ? cmd.substring(0, 27) + '...' : cmd;
        }
        return null;

      // Web search
      case 'web-search':
        match = content.match(/query=(?:"|')([^"|']+)(?:"|')/);
        return match
          ? match[1].length > 30
            ? match[1].substring(0, 27) + '...'
            : match[1]
          : null;

      // Data provider operations
      case 'call-data-provider':
        match = content.match(/service_name=(?:"|')([^"|']+)(?:"|')/);
        const route = content.match(/route=(?:"|')([^"|']+)(?:"|')/);
        return match && route
          ? `${match[1]}/${route[1]}`
          : match
            ? match[1]
            : null;

      // Deployment
      case 'deploy-site':
        match = content.match(/site_name=(?:"|')([^"|']+)(?:"|')/);
        return match ? match[1] : null;
    }

    return null;
  } catch (e) {
    console.warn('Error parsing tool parameters:', e);
    return null;
  }
};

const TOOL_DISPLAY_NAMES = new Map([
  ['execute-command', 'Executing Command'],
  ['check-command-output', 'Checking Command Output'],
  ['terminate-command', 'Terminating Command'],
  ['list-commands', 'Listing Commands'],
  
  ['create-file', 'Creating File'],
  ['delete-file', 'Deleting File'],
  ['full-file-rewrite', 'Rewriting File'],
  ['str-replace', 'Editing Text'],
  ['str_replace', 'Editing Text'],
  ['edit_file', 'Editing File'],
  ['edit-file', 'Editing File'],

  ['create-tasks', 'Creating Tasks'],
  ['update-tasks', 'Updating Tasks'],
  
  ['browser_navigate_to', 'Navigating to Page'],
  ['browser_act', 'Performing Action'],
  ['browser_extract_content', 'Extracting Content'],
  ['browser_screenshot', 'Taking Screenshot'],

  ['execute-data-provider-call', 'Calling data provider'],
  ['execute_data-provider_call', 'Calling data provider'],
  ['get-data-provider-endpoints', 'Getting endpoints'],
  
  ['deploy', 'Deploying'],
  ['ask', 'Ask'],
  ['create-tasks', 'Creating Tasks'],
  ['update-tasks', 'Updating Tasks'],
  ['complete', 'Completing Task'],
  ['crawl-webpage', 'Crawling Website'],
  ['expose-port', 'Exposing Port'],
  ['scrape-webpage', 'Scraping Website'],
  ['web-search', 'Searching Web'],
  ['see-image', 'Viewing Image'],
  ['create-presentation-outline', 'Creating Presentation Outline'],
  ['create-presentation', 'Creating Presentation'],

  ['create-sheet', 'Creating Sheet'],
  ['update-sheet', 'Updating Sheet'],
  ['view-sheet', 'Viewing Sheet'],
  ['analyze-sheet', 'Analyzing Sheet'],
  ['visualize-sheet', 'Visualizing Sheet'],
  ['format-sheet', 'Formatting Sheet'],
  

  ['update-agent', 'Updating Agent'],
  ['get-current-agent-config', 'Getting Agent Config'],
  ['search-mcp-servers', 'Searching MCP Servers'],
  ['get-mcp-server-tools', 'Getting MCP Server Tools'],
  ['configure-mcp-server', 'Configuring MCP Server'],
  ['get-popular-mcp-servers', 'Getting Popular MCP Servers'],
  ['test-mcp-server-connection', 'Testing MCP Server Connection'],

  ['get-project-structure', 'Getting Project Structure'],
  ['build-project', 'Building Project'],

  //V2

  ['execute_command', 'Executing Command'],
  ['check_command_output', 'Checking Command Output'],
  ['terminate_command', 'Terminating Command'],
  ['list_commands', 'Listing Commands'],
  
  ['create_file', 'Creating File'],
  ['delete_file', 'Deleting File'],
  ['full_file_rewrite', 'Rewriting File'],
  ['str_replace', 'Editing Text'],
  ['edit_file', 'Editing File'],
  
  ['browser_navigate_to', 'Navigating to Page'],
  ['browser_act', 'Performing Action'],
  ['browser_extract_content', 'Extracting Content'],
  ['browser_screenshot', 'Taking Screenshot'],

  ['execute_data_provider_call', 'Calling data provider'],
  ['get_data_provider_endpoints', 'Getting endpoints'],
  
  ['deploy', 'Deploying'],
  ['ask', 'Ask'],
  ['complete', 'Completing Task'],
  ['crawl_webpage', 'Crawling Website'],
  ['expose_port', 'Exposing Port'],
  ['scrape_webpage', 'Scraping Website'],
  ['web_search', 'Searching Web'],
  ['see_image', 'Viewing Image'],
  
  ['update_agent', 'Updating Agent'],
  ['get_current_agent_config', 'Getting Agent Config'],
  ['search_mcp_servers', 'Searching MCP Servers'],
  ['get_mcp_server_tools', 'Getting MCP Server Tools'],
  ['configure_mcp_server', 'Configuring MCP Server'],
  ['get_popular_mcp_servers', 'Getting Popular MCP Servers'],
  ['test_mcp_server_connection', 'Testing MCP Server Connection'],

]);


const MCP_SERVER_NAMES = new Map([
  ['exa', 'Exa Search'],
  ['github', 'GitHub'],
  ['notion', 'Notion'],
  ['slack', 'Slack'],
  ['filesystem', 'File System'],
  ['memory', 'Memory'],
]);

function formatMCPToolName(serverName: string, toolName: string): string {
  const serverMappings: Record<string, string> = {
    'exa': 'Exa Search',
    'github': 'GitHub',
    'notion': 'Notion', 
    'slack': 'Slack',
    'filesystem': 'File System',
    'memory': 'Memory',
    'anthropic': 'Anthropic',
    'openai': 'OpenAI',
    'composio': 'Composio',
    'langchain': 'LangChain',
    'llamaindex': 'LlamaIndex'
  };
  
  const formattedServerName = serverMappings[serverName.toLowerCase()] || 
    serverName.charAt(0).toUpperCase() + serverName.slice(1);
  
  let formattedToolName = toolName;
  
  if (toolName.includes('-')) {
    formattedToolName = toolName
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
  else if (toolName.includes('_')) {
    formattedToolName = toolName
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
  else if (/[a-z][A-Z]/.test(toolName)) {
    formattedToolName = toolName
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
  else {
    formattedToolName = toolName.charAt(0).toUpperCase() + toolName.slice(1);
  }
  
  return `${formattedServerName}: ${formattedToolName}`;
}

export function getUserFriendlyToolName(toolName: string): string {
  if (toolName.startsWith('mcp_')) {
    const parts = toolName.split('_');
    if (parts.length >= 3) {
      const serverName = parts[1];
      const toolNamePart = parts.slice(2).join('_');
      return formatMCPToolName(serverName, toolNamePart);
    }
  }
  if (toolName.includes('-') && !TOOL_DISPLAY_NAMES.has(toolName)) {
    const parts = toolName.split('-');
    if (parts.length >= 2) {
      const serverName = parts[0];
      const toolNamePart = parts.slice(1).join('-');
      return formatMCPToolName(serverName, toolNamePart);
    }
  }
  return TOOL_DISPLAY_NAMES.get(toolName) || toolName;
}

export const HIDE_STREAMING_XML_TAGS = new Set([
  'create-tasks',
  'execute-command',
  'create-file',
  'delete-file',
  'full-file-rewrite',
  'edit-file',
  'str-replace',
  'browser-click-element',
  'browser-close-tab',
  'browser-drag-drop',
  'browser-get-dropdown-options',
  'browser-go-back',
  'browser-input-text',
  'browser-navigate-to',
  'browser-scroll-down',
  'browser-scroll-to-text',
  'browser-scroll-up',
  'browser-select-dropdown-option',
  'browser-send-keys',
  'browser-switch-tab',
  'browser-wait',
  'deploy',
  'ask',
  'complete',
  'crawl-webpage',
  'web-search',
  'see-image',
  'execute_data_provider_call',
  'execute_data_provider_endpoint',

  'execute-data-provider-call',
  'execute-data-provider-endpoint',
]);
