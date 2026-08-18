import requests

def get_nasa_assets(keywords):
    search_url = f"https://images-api.nasa.gov/search?q={keywords}&media_type=video,image"
    try:
        response = requests.get(search_url).json()
        items = response.get('collection', {}).get('items', [])
        
        assets = []
        for item in items[:5]:
            nasa_id = item['data'][0]['nasa_id']
            media_type = item['data'][0]['media_type']
            
            manifest_url = f"https://images-api.nasa.gov/asset/{nasa_id}"
            manifest = requests.get(manifest_url).json()
            
            links = [file['href'] for file in manifest['collection']['items']]
            # Priority: Original MP4 -> Large JPG
            best_link = next((l for l in links if l.endswith('~orig.mp4')), 
                        next((l for l in links if l.endswith('~large.jpg')), None))
            
            if best_link:
                assets.append({"url": best_link, "type": media_type})
        return assets
    except Exception as e:
        print(f"Error fetching assets: {e}")
        return []
