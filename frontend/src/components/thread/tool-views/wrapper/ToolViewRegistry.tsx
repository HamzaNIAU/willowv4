import React, { useMemo } from 'react';
import { ToolViewProps } from '../types';
import { GenericToolView } from '../GenericToolView';
import { BrowserToolView } from '../BrowserToolView';
import { CommandToolView } from '../command-tool/CommandToolView';
import { CheckCommandOutputToolView } from '../command-tool/CheckCommandOutputToolView';
import { ExposePortToolView } from '../expose-port-tool/ExposePortToolView';
import { FileOperationToolView } from '../file-operation/FileOperationToolView';
import { FileEditToolView } from '../file-operation/FileEditToolView';
import { StrReplaceToolView } from '../str-replace/StrReplaceToolView';
import { WebCrawlToolView } from '../WebCrawlToolView';
import { WebScrapeToolView } from '../web-scrape-tool/WebScrapeToolView';
import { WebSearchToolView } from '../web-search-tool/WebSearchToolView';
import { SeeImageToolView } from '../see-image-tool/SeeImageToolView';
import { TerminateCommandToolView } from '../command-tool/TerminateCommandToolView';
import { AskToolView } from '../ask-tool/AskToolView';
import { CompleteToolView } from '../CompleteToolView';
import { ExecuteDataProviderCallToolView } from '../data-provider-tool/ExecuteDataProviderCallToolView';
import { DataProviderEndpointsToolView } from '../data-provider-tool/DataProviderEndpointsToolView';
import { DeployToolView } from '../DeployToolView';
import { SearchMcpServersToolView } from '../search-mcp-servers/search-mcp-servers';
import { GetAppDetailsToolView } from '../get-app-details/get-app-details';
import { CreateCredentialProfileToolView } from '../create-credential-profile/create-credential-profile';
import { ConnectCredentialProfileToolView } from '../connect-credential-profile/connect-credential-profile';
import { CheckProfileConnectionToolView } from '../check-profile-connection/check-profile-connection';
import { ConfigureProfileForAgentToolView } from '../configure-profile-for-agent/configure-profile-for-agent';
import { GetCredentialProfilesToolView } from '../get-credential-profiles/get-credential-profiles';
import { GetCurrentAgentConfigToolView } from '../get-current-agent-config/get-current-agent-config';
import { TaskListToolView } from '../task-list/TaskListToolView';
import { PresentationOutlineToolView } from '../PresentationOutlineToolView';
import { PresentationToolView } from '../PresentationToolView';
import { PresentationToolV2View } from '../PresentationToolV2View';
import { ListPresentationTemplatesToolView } from '../ListPresentationTemplatesToolView';
import { SheetsToolView } from '../sheets-tools/sheets-tool-view';
import { GetProjectStructureView } from '../web-dev/GetProjectStructureView';
import { ImageEditGenerateToolView } from '../image-edit-generate-tool/ImageEditGenerateToolView';
import { YouTubeToolView } from '../YouTubeToolView';
import { PinterestToolView } from '../PinterestToolView';
import { YouTubeUploadHistoryView } from '../YouTubeUploadHistoryView';
import { InstagramToolView } from '../InstagramToolView';
import { TwitterToolView } from '../TwitterToolView';
import { LinkedInToolView } from '../LinkedInToolView';
import { TikTokToolView } from '../TikTokToolView';


export type ToolViewComponent = React.ComponentType<ToolViewProps>;

type ToolViewRegistryType = Record<string, ToolViewComponent>;

const defaultRegistry: ToolViewRegistryType = {
  'browser-navigate-to': BrowserToolView,
  'browser-act': BrowserToolView,
  'browser-extract-content': BrowserToolView,
  'browser-screenshot': BrowserToolView,

  'execute-command': CommandToolView,
  'check-command-output': CheckCommandOutputToolView,
  'terminate-command': TerminateCommandToolView,
  'list-commands': GenericToolView,

  'create-file': FileOperationToolView,
  'delete-file': FileOperationToolView,
  'full-file-rewrite': FileOperationToolView,
  'read-file': FileOperationToolView,
  'edit-file': FileEditToolView,

  'str-replace': StrReplaceToolView,

  'web-search': WebSearchToolView,
  'crawl-webpage': WebCrawlToolView,
  'scrape-webpage': WebScrapeToolView,

  'execute-data-provider-call': ExecuteDataProviderCallToolView,
  'get-data-provider-endpoints': DataProviderEndpointsToolView,

  'search-mcp-servers': SearchMcpServersToolView,
  'get-app-details': GetAppDetailsToolView,
  'create-credential-profile': CreateCredentialProfileToolView,
  'connect-credential-profile': ConnectCredentialProfileToolView,
  'check-profile-connection': CheckProfileConnectionToolView,
  'configure-profile-for-agent': ConfigureProfileForAgentToolView,
  'get-credential-profiles': GetCredentialProfilesToolView,
  'get-current-agent-config': GetCurrentAgentConfigToolView,
  'create-tasks': TaskListToolView,
  'view-tasks': TaskListToolView,
  'update-tasks': TaskListToolView,
  'delete-tasks': TaskListToolView,
  'clear-all': TaskListToolView,


  'expose-port': ExposePortToolView,

  'see-image': SeeImageToolView,
  'image-edit-or-generate': ImageEditGenerateToolView,

  'ask': AskToolView,
  'complete': CompleteToolView,

  'deploy': DeployToolView,

  'create-presentation-outline': PresentationOutlineToolView,
  'create-presentation': PresentationToolV2View,
  'export-presentation': PresentationToolV2View,
  'list-presentation-templates': ListPresentationTemplatesToolView,
  
  'create-sheet': SheetsToolView,
  'update-sheet': SheetsToolView,
  'view-sheet': SheetsToolView,
  'analyze-sheet': SheetsToolView,
  'visualize-sheet': SheetsToolView,
  'format-sheet': SheetsToolView,

  // YouTube tool views - all variations for compatibility
  // Hyphenated versions (what the XML parser converts to)
  'youtube-authenticate': YouTubeToolView,
  'youtube-channels': YouTubeToolView,
  'youtube-upload-video': YouTubeToolView,
  'youtube-list-captions': YouTubeToolView,
  'youtube-download-caption': YouTubeToolView,
  'youtube-list-channel-videos': YouTubeToolView,
  'youtube-list-playlists': YouTubeToolView,
  'youtube-list-subscriptions': YouTubeToolView,
  'youtube-subscribe-channel': YouTubeToolView,
  'youtube-manage-video': YouTubeToolView,
  'youtube-smart-search': YouTubeToolView,
  'youtube-check-upload-status': YouTubeUploadHistoryView,
  
  // Underscore versions (actual backend tool names)
  'youtube_authenticate': YouTubeToolView,
  'youtube_channels': YouTubeToolView,
  'youtube_upload_video': YouTubeToolView,
  'youtube_list_captions': YouTubeToolView,
  'youtube_download_caption': YouTubeToolView,
  'youtube_list_channel_videos': YouTubeToolView,
  'youtube_list_playlists': YouTubeToolView,
  'youtube_list_subscriptions': YouTubeToolView,
  'youtube_subscribe_channel': YouTubeToolView,
  'youtube_manage_video': YouTubeToolView,
  'youtube_smart_search': YouTubeToolView,
  'youtube_check_upload_status': YouTubeUploadHistoryView,

  // Pinterest tool views
  // Hyphenated versions
  'pinterest-authenticate': PinterestToolView,
  'pinterest-accounts': PinterestToolView,
  'pinterest-create-pin': PinterestToolView,
  'pinterest-pin-status': PinterestToolView,
  'pinterest-account-boards': PinterestToolView,
  'pinterest-recent-pins': PinterestToolView,
  // Underscore versions
  'pinterest_authenticate': PinterestToolView,
  'pinterest_accounts': PinterestToolView,
  'pinterest_create_pin': PinterestToolView,
  'pinterest_pin_status': PinterestToolView,
  'pinterest_account_boards': PinterestToolView,
  'pinterest_recent_pins': PinterestToolView,

  // Instagram
  'instagram-authenticate': InstagramToolView,
  'instagram-accounts': InstagramToolView,
  'instagram-create-post': InstagramToolView,
  'instagram-create-story': InstagramToolView,
  'instagram-get-posts': InstagramToolView,
  'instagram_authenticate': InstagramToolView,
  'instagram_accounts': InstagramToolView,
  'instagram_create_post': InstagramToolView,
  'instagram_create_story': InstagramToolView,
  'instagram_get_posts': InstagramToolView,

  // Twitter (X)
  'twitter-authenticate': TwitterToolView,
  'twitter-accounts': TwitterToolView,
  'twitter-create-tweet': TwitterToolView,
  'twitter-check-tweet-status': TwitterToolView,
  'twitter-search-tweets': TwitterToolView,
  'twitter_authenticate': TwitterToolView,
  'twitter_accounts': TwitterToolView,
  'twitter_create_tweet': TwitterToolView,
  'twitter_check_tweet_status': TwitterToolView,
  'twitter_search_tweets': TwitterToolView,

  // LinkedIn
  'linkedin-authenticate': LinkedInToolView,
  'linkedin-accounts': LinkedInToolView,
  'linkedin-create-post': LinkedInToolView,
  'linkedin-post-status': LinkedInToolView,
  'linkedin-account-posts': LinkedInToolView,
  'linkedin-auth': LinkedInToolView,
  'linkedin_authenticate': LinkedInToolView,
  'linkedin_accounts': LinkedInToolView,
  'linkedin_create_post': LinkedInToolView,
  'linkedin_post_status': LinkedInToolView,
  'linkedin_account_posts': LinkedInToolView,

  // TikTok
  'tiktok-authenticate': TikTokToolView,
  'tiktok-accounts': TikTokToolView,
  'tiktok-upload-video': TikTokToolView,
  'tiktok_authenticate': TikTokToolView,
  'tiktok_accounts': TikTokToolView,
  'tiktok_upload_video': TikTokToolView,

  'get-project-structure': GetProjectStructureView,
  'list-web-projects': GenericToolView,

  'default': GenericToolView,
};

class ToolViewRegistry {
  private registry: ToolViewRegistryType;

  constructor(initialRegistry: Partial<ToolViewRegistryType> = {}) {
    this.registry = { ...defaultRegistry };

    Object.entries(initialRegistry).forEach(([key, value]) => {
      if (value !== undefined) {
        this.registry[key] = value;
      }
    });
  }

  register(toolName: string, component: ToolViewComponent): void {
    this.registry[toolName] = component;
  }

  registerMany(components: Partial<ToolViewRegistryType>): void {
    Object.assign(this.registry, components);
  }

  get(toolName: string): ToolViewComponent {
    return this.registry[toolName] || this.registry['default'];
  }

  has(toolName: string): boolean {
    return toolName in this.registry;
  }

  getToolNames(): string[] {
    return Object.keys(this.registry).filter(key => key !== 'default');
  }

  clear(): void {
    this.registry = { default: this.registry['default'] };
  }
}

export const toolViewRegistry = new ToolViewRegistry();

export function useToolView(toolName: string): ToolViewComponent {
  return useMemo(() => toolViewRegistry.get(toolName), [toolName]);
}

export function ToolView({ name = 'default', ...props }: ToolViewProps) {
  const ToolViewComponent = useToolView(name);
  return <ToolViewComponent name={name} {...props} />;
}
