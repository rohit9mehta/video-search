import scrapetube

# gather all YouTube video links from channel
def fetch_all_videos_yt(channel_url):
    # TODO
    videos = scrapetube.get_channel(channel_url=channel_url)
    # need to preface each with 'https://www.youtube.com/watch?v=' 
    return [video['videoId'] for video in videos]

# print(fetch_all_videos_yt("https://www.youtube.com/@MusicForTheSoul11/"))