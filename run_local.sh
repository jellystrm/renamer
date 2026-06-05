# 1. Cài đặt thư viện
pip install -r requirements.txt

# 2. Tạo thư mục test (nếu chưa có)
mkdir -p test_media/movies test_media/tv
mkdir -p "test_media/movies/Inception.2010.1080p"
mkdir -p "test_media/tv/The.Boys.S01.2019"

# 3. Tạo file .env để cấu hình local
cat <<EOF > .env
TMDB_API_KEY=your_tmdb_api_key_here
MOVIE_DIR=$(pwd)/test_media/movies
TV_DIR=$(pwd)/test_media/tv
EOF

# 4. Chạy server
uvicorn main:app --host 0.0.0.0 --port 8099 --reload
