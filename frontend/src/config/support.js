import { i18n } from '../i18n/index.js';

const pageText = (...args) => i18n.global.t(...args);

/**
 * ARL-Next 赞助打赏、公众号与作者微信支持配置
 * 
 * 💡 二维码图片替换指引：
 * 只要将您的真实二维码截图放置在 `frontend/src/assets/support/` 目录下即可自动被检测识别：
 *   - 打赏收款码：reward.png 或 reward.jpg
 *   - 官方公众号：mp.png 或 mp.jpg
 *   - 作者微信号：wechat.png 或 wechat.jpg
 * 若未放置真实 png/jpg，系统会自动优雅回退展示对应的矢量占位图。
 */

export const SUPPORT_CONFIG = {
  // 顶部导航栏入口文案与提示
  entry: {
    get text() { return pageText('pages.supportTheAuthor'); },
    icon: '💖',
    get tooltip() { return pageText('pages.followTheOfficialAccountJoinTheCommunityAndSupport'); },
    showPulse: true, // 是否启用轻量心跳呼吸微光
  },

  // 默认激活的 Tab ('reward' | 'official' | 'wechat')
  defaultTab: 'reward',

  // 1. 赞助打赏配置
  reward: {
    get tabTitle() { return pageText('pages.sponsor'); },
    get badge() { return pageText('pages.buyACoffee'); },
    get title() { return pageText('pages.supportOngoingArlNextMaintenance'); },
    get desc() { return pageText('pages.ifArlNextHelpsWithYourAssetDiscoveryAnd'); },
    get subText() { return pageText('pages.scanWithWechatPayAlipayToSupport'); },
  },

  // 2. 官方公众号配置
  official: {
    get tabTitle() { return pageText('pages.officialAccountLabel2'); },
    get badge() { return pageText('pages.latestNews'); },
    get title() { return pageText('pages.followTheOfficialWechatAccount'); },
    name: 'owl安全',
    get desc() { return pageText('pages.getUpdatesOnArlNextReleasesFingerprintLibrariesAnd'); },
    get subText() { return pageText('pages.scanWithWechatToFollow'); },
  },

  // 3. 作者微信号 / 交流群配置
  wechat: {
    get tabTitle() { return pageText('pages.communityAndFeedback'); },
    get badge() { return pageText('pages.technicalDiscussion'); },
    get title() { return pageText('pages.addTheAuthorOnWechatJoinTheCommunity'); },
    wechatId: 'owl234234', // 请替换为您的实际微信号
    get desc() { return pageText('pages.addTheAuthorOnWechatToDiscussAssetDiscovery'); },
    get subText() { return pageText('pages.scanWithWechatToAddTheAuthorIncludeArl'); },
  }
};
