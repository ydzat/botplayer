"""
基于 MusicFree 实现的真实 Bilibili 音源
"""
import asyncio
import aiohttp
import hashlib
import hmac
import json
import time
import re
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import quote
from .models import Song

logger = logging.getLogger(__name__)


class BilibiliMusicSource:
    """真实的 Bilibili 音乐源实现"""
    
    def __init__(self):
        self.cookie_cache = None
        self.wbi_keys_cache = None
        self.wbi_keys_time = None
        
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        }
        
        self.search_headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "origin": "https://search.bilibili.com",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://search.bilibili.com/",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        }
    
    async def get_cookie(self):
        """获取必要的 cookie"""
        if self.cookie_cache:
            return self.cookie_cache
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.bilibili.com/x/frontend/finger/spi",
                    headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1 Edg/114.0.0.0"
                    }
                ) as response:
                    data = await response.json()
                    if data.get('code') == 0:
                        self.cookie_cache = data['data']
                        return self.cookie_cache
        except Exception as e:
            logger.error(f"获取 cookie 失败: {e}")
        
        return None
    
    def get_mixin_key(self, origin: str) -> str:
        """获取混合密钥"""
        mixin_key_enc_tab = [
            46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
            33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
            61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
            36, 20, 34, 44, 52
        ]
        
        return ''.join([origin[i] for i in mixin_key_enc_tab if i < len(origin)])[:32]
    
    def hmac_sha256(self, key: str, message: str) -> str:
        """HMAC-SHA256 签名"""
        return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    
    async def get_bili_ticket(self, csrf: str = '') -> Optional[dict]:
        """获取 bili_ticket"""
        try:
            ts = int(time.time())
            hex_sign = self.hmac_sha256('XgwSnGZ1p', f'ts{ts}')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket',
                    params={
                        'key_id': 'ec02',
                        'hexsign': hex_sign,
                        'context[ts]': ts,
                        'csrf': csrf
                    },
                    headers={
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0'
                    }
                ) as response:
                    data = await response.json()
                    return data.get('data')
        except Exception as e:
            logger.error(f"获取 bili_ticket 失败: {e}")
            return None
    
    async def get_wbi_keys(self) -> Optional[dict]:
        """获取 WBI 密钥"""
        # 检查缓存
        if (self.wbi_keys_cache and self.wbi_keys_time and 
            time.time() - self.wbi_keys_time < 3600):  # 1小时有效期
            return self.wbi_keys_cache
        
        try:
            ticket_data = await self.get_bili_ticket()
            if not ticket_data or 'nav' not in ticket_data:
                return None
            
            img_url = ticket_data['nav']['img']
            sub_url = ticket_data['nav']['sub']
            
            img_key = img_url.split('/')[-1].split('.')[0]
            sub_key = sub_url.split('/')[-1].split('.')[0]
            
            self.wbi_keys_cache = {'img': img_key, 'sub': sub_key}
            self.wbi_keys_time = time.time()
            
            return self.wbi_keys_cache
            
        except Exception as e:
            logger.error(f"获取 WBI 密钥失败: {e}")
            return None
    
    async def get_w_rid(self, params: dict) -> str:
        """生成 w_rid 签名"""
        try:
            wbi_keys = await self.get_wbi_keys()
            if not wbi_keys:
                return ''
            
            mixin_key = self.get_mixin_key(wbi_keys['img'] + wbi_keys['sub'])
            
            # 排序参数
            sorted_params = sorted(params.items())
            
            # 构建查询字符串
            query_parts = []
            for key, value in sorted_params:
                if value is not None:
                    # 过滤特殊字符
                    if isinstance(value, str):
                        value = re.sub(r"[!'\(\)*]", "", value)
                    query_parts.append(f"{quote(str(key))}={quote(str(value))}")
            
            query_string = '&'.join(query_parts) + mixin_key
            
            # MD5 哈希
            w_rid = hashlib.md5(query_string.encode()).hexdigest()
            return w_rid
            
        except Exception as e:
            logger.error(f"生成 w_rid 失败: {e}")
            return ''
    
    def duration_to_sec(self, duration) -> int:
        """将时长转换为秒数"""
        if isinstance(duration, int):
            return duration
        
        if isinstance(duration, str):
            parts = duration.split(':')
            try:
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (ValueError, IndexError):
                pass
        
        return 0
    
    def format_media(self, result: dict) -> Song:
        """格式化搜索结果为 Song 对象"""
        try:
            # 清理标题中的 HTML 标签
            title = result.get('title', '')
            title = re.sub(r'<[^>]+>', '', title)
            title = re.sub(r'\s+', ' ', title).strip()
            
            # 获取封面图片
            pic = result.get('pic', '')
            if pic.startswith('//'):
                pic = f'https:{pic}'
            
            song = Song(
                id=result.get('bvid', result.get('aid', '')),
                title=title,
                artist=result.get('author', '未知艺术家'),
                album='Bilibili',
                duration=self.duration_to_sec(result.get('duration', 0)),
                platform='bilibili',
                artwork=pic,
                url=f"https://www.bilibili.com/video/{result.get('bvid', result.get('aid', ''))}",
                extra={
                    'bvid': result.get('bvid', ''),
                    'aid': result.get('aid', ''),
                    'cid': result.get('cid', ''),
                    'view_count': result.get('play', 0),
                    'description': result.get('description', '')[:200] + '...' if len(result.get('description', '')) > 200 else result.get('description', ''),
                    'pubdate': result.get('pubdate', 0)
                }
            )
            
            return song
            
        except Exception as e:
            logger.error(f"格式化媒体信息失败: {e}")
            return None
    
    def is_music_related(self, title: str, description: str = '') -> bool:
        """判断是否为音乐相关内容"""
        music_keywords = [
            '音乐', 'music', '歌', 'song', '翻唱', 'cover', 'mv', 'live',
            '演唱', '钢琴', 'piano', '吉他', 'guitar', '小提琴', 'violin',
            '纯音乐', 'bgm', '背景音乐', '原创', 'original', '伴奏',
            '歌词', 'lyrics', '主题曲', '插曲', '配乐', 'ost', '音乐节',
            '歌手', '歌曲', '专辑', 'album', '单曲', 'single', '作曲', '作词'
        ]
        
        text = (title + ' ' + description).lower()
        return any(keyword in text for keyword in music_keywords)
    
    async def search(self, keyword: str, page: int = 1, limit: int = 10) -> List[Song]:
        """搜索音乐"""
        try:
            # 获取 cookie
            cookie_data = await self.get_cookie()
            if not cookie_data:
                logger.warning("无法获取 cookie，使用简化搜索")
                return await self._simple_search(keyword, page, limit)
            
            # 构建搜索参数
            params = {
                'context': '',
                'page': page,
                'order': '',
                'page_size': min(limit * 2, 50),  # 多搜索一些用于过滤
                'keyword': keyword,  # 移除自动添加的"音乐"关键词，避免重复
                'duration': '',
                'tids_1': '',
                'tids_2': '',
                '__refresh__': 'true',
                '_extra': '',
                'highlight': 1,
                'single_column': 0,
                'platform': 'pc',
                'from_source': '',
                'search_type': 'video',
                'dynamic_offset': 0
            }
            
            # 添加 cookie 到 headers
            headers = self.search_headers.copy()
            headers['cookie'] = f"buvid3={cookie_data['b_3']};buvid4={cookie_data['b_4']}"
            
            results = []
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.bilibili.com/x/web-interface/search/type",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == 0 and 'data' in data:
                            search_results = data['data'].get('result', [])
                            
                            for item in search_results:
                                if len(results) >= limit:
                                    break
                                
                                # 基本验证
                                if not item.get('bvid') and not item.get('aid'):
                                    continue
                                
                                # 时长过滤
                                duration = self.duration_to_sec(item.get('duration', 0))
                                if duration < 10 or duration > 1800:  # 10秒到30分钟
                                    continue
                                
                                # 音乐相关性过滤
                                title = item.get('title', '')
                                description = item.get('description', '')
                                if not self.is_music_related(title, description):
                                    continue
                                
                                song = self.format_media(item)
                                if song:
                                    results.append(song)
                                    logger.info(f"找到音乐: {song.title} - {song.artist}")
                    
                    else:
                        logger.warning(f"Bilibili API 返回状态码: {response.status}")
                        return await self._simple_search(keyword, page, limit)
            
            # 如果 API 搜索成功但没有找到合适的结果，使用备用搜索
            if not results:
                logger.info("API 搜索无合适结果，使用备用搜索方案")
                return await self._simple_search(keyword, page, limit)
            
            return results
            
        except Exception as e:
            logger.error(f"Bilibili 搜索失败: {e}")
            return await self._simple_search(keyword, page, limit)
    
    async def _simple_search(self, keyword: str, page: int, limit: int) -> List[Song]:
        """简化搜索（使用 yt-dlp 备用方案）"""
        try:
            # 先尝试使用基础 API
            params = {
                'search_type': 'video',
                'keyword': keyword,  # 移除自动添加的"音乐"关键词
                'page': page
            }
            
            # 使用更真实的请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://search.bilibili.com/',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.bilibili.com/x/web-interface/search/type",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == 0 and 'data' in data:
                            search_results = data['data'].get('result', [])
                            results = []
                            
                            for item in search_results:
                                if len(results) >= limit:
                                    break
                                
                                # 基本过滤
                                if not item.get('bvid') and not item.get('aid'):
                                    continue
                                
                                duration = self.duration_to_sec(item.get('duration', 0))
                                if duration < 30 or duration > 600:
                                    continue
                                
                                title = item.get('title', '')
                                if not self.is_music_related(title):
                                    continue
                                
                                song = self.format_media(item)
                                if song:
                                    results.append(song)
                                    logger.info(f"API搜索找到: {song.title} - {song.artist}")
                            
                            if results:
                                return results
                    
                    else:
                        logger.warning(f"Bilibili API 返回状态码: {response.status}")
            
            # 如果 API 搜索失败，使用 yt-dlp 备用方案
            logger.info("API 搜索失败，尝试使用 yt-dlp 备用方案...")
            return await self._fallback_search_ytdlp(keyword, page, limit)
            
        except Exception as e:
            logger.error(f"简化搜索失败: {e}")
            # 使用 yt-dlp 备用方案
            return await self._fallback_search_ytdlp(keyword, page, limit)
    
    async def _fallback_search_ytdlp(self, keyword: str, page: int, limit: int) -> List[Song]:
        """使用 yt-dlp 的备用搜索方案"""
        try:
            import yt_dlp
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            def search_with_ytdlp():
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,  # 改为 False 以获取完整信息
                    'skip_download': True,
                    'playlistend': limit,
                }
                
                # 使用正确的 bilisearch 语法
                search_url = f"bilisearch:{keyword}"
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        search_results = ydl.extract_info(search_url, download=False)
                        return search_results
                except Exception as e:
                    logger.error(f"yt-dlp 搜索失败: {e}")
                    return None
            
            # 在线程池中运行 yt-dlp 搜索
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                search_results = await loop.run_in_executor(executor, search_with_ytdlp)
            
            if search_results and 'entries' in search_results:
                results = []
                valid_entries = [entry for entry in search_results['entries'] if entry is not None]
                
                logger.info(f"yt-dlp 找到 {len(valid_entries)} 个原始结果")
                
                for entry in valid_entries[:limit]:
                    # 跳过无效的条目
                    if not entry or not entry.get('title'):
                        continue
                    
                    # 如果标题是"未知"，跳过
                    title = entry.get('title', '')
                    if title in ['未知', 'Unknown', '']:
                        continue
                    
                    # 构建视频 ID 和 URL
                    video_id = entry.get('id', '')
                    if video_id and not video_id.startswith('BV'):
                        # 如果是 AV 号，转换为完整 URL
                        video_url = f"https://www.bilibili.com/video/av{video_id}"
                    elif video_id.startswith('BV'):
                        video_url = f"https://www.bilibili.com/video/{video_id}"
                    else:
                        video_url = entry.get('webpage_url', entry.get('url', ''))
                    
                    # 提取艺术家信息
                    artist = entry.get('uploader', entry.get('creator', '未知UP主'))
                    
                    # 构建 Song 对象
                    song = Song(
                        id=video_id,
                        title=title,
                        artist=artist,
                        album='Bilibili',
                        duration=entry.get('duration', 0) or 0,
                        platform='bilibili',
                        url=video_url,
                        artwork=entry.get('thumbnail', ''),
                        extra={
                            'view_count': entry.get('view_count', 0),
                            'like_count': entry.get('like_count', 0),
                            'description': entry.get('description', ''),
                            'upload_date': entry.get('upload_date', ''),
                            'uploader_id': entry.get('uploader_id', ''),
                        }
                    )
                    
                    results.append(song)
                    logger.info(f"yt-dlp搜索找到: {song.title} - {song.artist}")
                
                if results:
                    logger.info(f"yt-dlp 返回 {len(results)} 个有效结果")
                    return results
                else:
                    logger.warning("yt-dlp 搜索无有效结果")
                        
        except ImportError:
            logger.warning("yt-dlp 未安装，无法使用备用搜索")
        except Exception as e:
            logger.error(f"yt-dlp 备用搜索失败: {e}")
            import traceback
            traceback.print_exc()
        
        return []
    
    async def get_play_url(self, song: Song) -> Optional[str]:
        """获取播放链接"""
        # 返回原始链接，让 yt-dlp 处理
        return song.url
