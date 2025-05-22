import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from PIL import Image

# --- 데이터베이스 설정 ---
DB_FILE = 'db.db' # 데이터베이스 파일 이름

def get_db_connection():
    """SQLite 데이터베이스 연결을 생성하고 반환합니다."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row # 결과를 딕셔너리처럼 접근할 수 있게 설정
    return conn

def init_db():
    """
    데이터베이스 파일을 생성하고 필요한 테이블을 초기화합니다.
    앱이 처음 실행될 때 한 번 호출됩니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. movies 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            director TEXT,
            release_year INTEGER,
            poster_url TEXT,
            genre TEXT,
            trailer_url TEXT
        )
    """)

    # 2. reviews 테이블 생성 (user_id 컬럼 없음)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            review_text TEXT,
            watch_date TEXT,
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

# --- 리뷰 추가 함수 ---
def add_review_to_db(movie_id, rating, review_text, watch_date):
    """리뷰 데이터를 데이터베이스에 추가합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO reviews (movie_id, rating, review_text, watch_date) VALUES (?, ?, ?, ?)",
            (movie_id, rating, review_text, watch_date)
        )
        conn.commit()
        st.success("리뷰가 성공적으로 제출되었습니다!")
        return True
    except sqlite3.Error as e:
        st.error(f"리뷰 제출 중 오류 발생: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

# --- Streamlit 앱 시작 설정 ---
st.set_page_config(layout="wide", page_title="모두의 영화 평점")

# 세션 상태 초기화 (페이지 전환 시 데이터 유지 위함)
if 'page' not in st.session_state:
    st.session_state["page"] = 'home'
if 'selected_movie_id' not in st.session_state:
    st.session_state.selected_movie_id = None

# --- 사이드바 네비게이션 ---
st.sidebar.title("메뉴")
if st.sidebar.button("🏠 홈", key="nav_home"):
    st.session_state["page"] = 'home'
    st.session_state.selected_movie_id = None # 홈으로 돌아갈 때 선택된 영화 초기화
    st.rerun()
if st.sidebar.button("➕ 영화 추가", key="nav_add_movie"):
    st.session_state["page"] = 'add_movie'
    st.session_state.selected_movie_id = None
    st.rerun()
if st.sidebar.button("📊 통계 보기", key="nav_stats"):
    st.session_state["page"] = 'stats'
    st.session_state.selected_movie_id = None
    st.rerun()

st.title("🎬 모두의 영화 평점 사이트")

# --- 페이지 라우팅 로직 ---

if st.session_state["page"] == 'home':
    st.header("등록된 영화 목록")
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # 모든 영화 정보와 각 영화의 평균 평점을 함께 가져옵니다.
            # 리뷰가 없는 영화도 표시하기 위해 LEFT JOIN 사용
            cursor.execute("""
                SELECT
                    m.id,
                    m.title,
                    m.director,
                    m.release_year,
                    m.poster_url,
                    AVG(r.rating) AS avg_rating,
                    COUNT(r.id) AS review_count
                FROM
                    movies m
                LEFT JOIN
                    reviews r ON m.id = r.movie_id
                GROUP BY
                    m.id, m.title, m.director, m.release_year, m.poster_url
                ORDER BY
                    m.title ASC
            """)
            all_movies_raw = cursor.fetchall()

            if all_movies_raw:
                # pandas DataFrame으로 변환하여 데이터 처리 용이
                all_movies = pd.DataFrame([dict(row) for row in all_movies_raw])

                # 영화 목록을 그리드 형태로 표시
                cols_per_row = 3 # 한 줄에 3개의 영화 카드
                
                num_rows = (len(all_movies) + cols_per_row - 1) // cols_per_row
                
                for r_idx in range(num_rows):
                    cols = st.columns(cols_per_row)
                    for c_idx in range(cols_per_row):
                        movie_index = r_idx * cols_per_row + c_idx
                        if movie_index < len(all_movies):
                            movie_row = all_movies.iloc[movie_index]
                            with cols[c_idx]:
                                # 영화 카드 영역 (클릭 가능하도록 버튼 활용)
                                with st.container(border=True): # 시각적인 구분을 위해 컨테이너 사용
                                    # 영화 포스터 이미지
                                    if movie_row['poster_url']:
                                        st.image(movie_row['poster_url'], caption=movie_row['title'], width=150)
                                    else:
                                        # 포스터가 없을 경우 대체 텍스트와 함께 제목 표시
                                        st.markdown(f"**{movie_row['title']}**")
                                        st.write("_(포스터 없음)_")
                                    
                                    # 영화 제목 (링크처럼 보이게)
                                    st.markdown(f"**[{movie_row['title']}](.)**", 
                                                help="클릭하여 상세 페이지로 이동",
                                                unsafe_allow_html=True) # 마크다운 링크 사용

                                    # 평균 평점 표시
                                    if movie_row['avg_rating']:
                                        # 별 이모지와 함께 소수점 첫째 자리까지 표시
                                        st.write(f"⭐ 평균 평점: **{movie_row['avg_rating']:.1f}**")
                                        st.caption(f"({int(movie_row['review_count'])}명 참여)")
                                    else:
                                        st.write("아직 평점이 없습니다.")

                                    # 상세보기 버튼 (컨테이너 내에 배치)
                                    if st.button("상세보기", key=f"view_detail_{movie_row['id']}", use_container_width=True):
                                        st.session_state["selected_movie_id"] = movie_row['id']
                                        st.session_state["page"] = 'movie_detail'
                                        st.rerun() 
                st.markdown("---")
            else:
                st.info("아직 등록된 영화가 없습니다. '영화 추가' 메뉴에서 새로운 영화를 추가해보세요!")

        except sqlite3.Error as err:
            st.error(f"영화 목록을 불러오는 중 오류 발생: {err}")
        finally:
            cursor.close()
            conn.close()

elif st.session_state["page"] == 'movie_detail' and st.session_state.selected_movie_id:
    movie_id = st.session_state.selected_movie_id
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM movies WHERE id = {movie_id}")
            movie_raw = cursor.fetchone()
            movie = dict(movie_raw) if movie_raw else None

            if movie:
                st.header(f"'{movie['title']}' 상세 정보")
                col1, col2 = st.columns([1, 2])
                with col1:
                    if movie['poster_url']:
                        st.image(movie['poster_url'], caption=movie['title'], width=200)
                    else:
                        st.write("포스터 없음")
                with col2:
                    st.write(f"**감독:** {movie['director']}")
                    st.write(f"**개봉 연도:** {movie['release_year']}")
                    
                    if movie['genre']:
                        genres = [g.strip() for g in movie['genre'].split(',') if g.strip()]
                        if genres:
                            st.write("**장르:**")
                            st.pills("genres_pill", genres, label_visibility="collapsed")
                        else:
                            st.write("**장르:** 미상")
                    else:
                        st.write("**장르:** 미상")

                    if movie['trailer_url']:
                        st.subheader("예고편")
                        # You may need a more robust YouTube URL parsing here if your URLs are not standard
                        # Streamlit's st.video often expects standard YouTube watch URLs (e.g., https://www.youtube.com/watch?v=VIDEO_ID)
                        # or direct video file URLs.
                        # The placeholder `youtu.be/2` is not a valid YouTube URL.
                        # For now, let's assume valid YouTube URLs will be provided by the user.
                        # If you consistently use non-standard URLs like your original `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
                        # you will need a function to extract the actual YouTube video ID from them.
                        
                        # A common way to embed YouTube videos in Streamlit is to use the direct URL:
                        # e.g., st.video("https://www.youtube.com/watch?v=VIDEO_ID")
                        # If you have non-standard URLs, you might need to parse them first.
                        # For example:
                        # if "watch?v=" in movie['trailer_url']:
                        #     youtube_id = movie['trailer_url'].split("watch?v=")[-1].split("&")[0]
                        #     st.video(f"https://www.youtube.com/watch?v={youtube_id}")
                        # else:
                        #     st.warning("Invalid YouTube URL format.")
                        #     st.write(f"Provided URL: `{movie['trailer_url']}`")
                        
                        # For now, I'll keep the direct `st.video` call, assuming valid URLs will be used.
                        # Please ensure your trailer_url values in the DB are standard YouTube watch URLs.
                        st.video(movie['trailer_url']) # Assuming valid YouTube watch URL is stored
                    else:
                        st.info("등록된 예고편이 없습니다.")

                st.markdown("---")
                st.subheader("모두의 리뷰")

                cursor.execute("SELECT * FROM reviews WHERE movie_id = ? ORDER BY watch_date DESC, id DESC", (movie_id,))
                reviews_raw = cursor.fetchall()
                if reviews_raw:
                    reviews = pd.DataFrame([dict(row) for row in reviews_raw])
                else:
                    reviews = pd.DataFrame()

                if not reviews.empty:
                    avg_rating = reviews['rating'].mean()
                    st.metric(label="현재 평균 평점", value=f"{avg_rating:.1f}점", delta=f"{len(reviews)}개 리뷰")
                    
                    st.markdown("---")
                    st.subheader("전체 리뷰 목록")
                    for i, review in reviews.iterrows():
                        st.write(f"**평점:** {'⭐' * review['rating']} ({review['rating']}/5)")
                        st.write(f"**본 날짜:** {review['watch_date']}")
                        if review['review_text']:
                            st.text_area("리뷰 내용", review['review_text'], height=70, disabled=True, key=f"review_text_display_{review['id']}")
                        st.markdown("---")
                else:
                    st.info("아직 이 영화에 대한 리뷰가 없습니다. 아래에서 첫 번째 평점을 남겨주세요!")

                st.subheader("이 영화에 평점을 남겨주세요!")
                st.write("별을 클릭하여 평점을 선택하고, 리뷰 내용을 작성한 후 '리뷰 제출' 버튼을 눌러주세요.")

                with st.form("movie_review_form", clear_on_submit=True):
                    selected_stars_index = st.feedback("stars", key=f"feedback_stars_{movie_id}") 
                    review_text_input = st.text_area("리뷰 내용", help="영화에 대한 자세한 감상을 작성해주세요.", key=f"review_text_area_{movie_id}")
                    watch_date_input = st.date_input("영화를 본 날짜 (선택 사항)", datetime.now().date(), help="이 영화를 언제 보셨나요?", key=f"watch_date_input_{movie_id}")
                    submit_button = st.form_submit_button("리뷰 제출", key=f"submit_review_button_{movie_id}")

                    if submit_button:
                        if selected_stars_index is None:
                            st.warning("별점을 선택해주세요!")
                        else:
                            rating_value = selected_stars_index + 1
                            if add_review_to_db(movie_id, rating_value, review_text_input, watch_date_input.strftime('%Y-%m-%d')):
                                st.rerun()

            else:
                st.error("선택된 영화를 찾을 수 없습니다. 홈으로 돌아갑니다.")
                #st.session_state["page"] = 'home'
                #st.rerun()

        except sqlite3.Error as err:
            st.error(f"영화 상세 정보를 불러오는 중 오류 발생: {err}")
        finally:
            cursor.close()
            conn.close()

elif st.session_state["page"] == 'add_movie':
    st.header("새 영화 추가하기")
    with st.form("add_movie_form", clear_on_submit=True):
        title = st.text_input("영화 제목", key="movie_title_input")
        director = st.text_input("감독", key="movie_director_input")
        release_year = st.number_input("개봉 연도", min_value=1800, max_value=datetime.now().year + 5, value=datetime.now().year, key="movie_year_input")
        genre = st.text_input("장르 (쉼표로 구분, 예: 액션, SF)", key="movie_genre_input")
        poster_url = st.text_input("포스터 URL (선택 사항)", placeholder="https://example.com/poster.jpg", key="movie_poster_input")
        trailer_url = st.text_input("예고편 URL (선택 사항, YouTube 링크)", placeholder="youtu.be/3", key="movie_trailer_input")

        submitted = st.form_submit_button("영화 추가")

        if submitted:
            if not title:
                st.warning("영화 제목은 필수로 입력해야 합니다.")
            else:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "INSERT INTO movies (title, director, release_year, genre, poster_url, trailer_url) VALUES (?, ?, ?, ?, ?, ?)",
                            (title, director, release_year, genre, poster_url, trailer_url)
                        )
                        conn.commit()
                        st.success(f"'{title}' 영화가 성공적으로 추가되었습니다!")
                        st.session_state["page"] = 'home'
                        st.rerun()
                    except sqlite3.Error as err:
                        st.error(f"영화 추가 중 오류 발생: {err}")
                        conn.rollback()
                    finally:
                        cursor.close()
                        conn.close()

elif st.session_state["page"] == 'stats':
    st.header("영화 평점 통계")
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # 1. 평점 분포
            cursor.execute("SELECT rating, COUNT(*) as count FROM reviews GROUP BY rating ORDER BY rating")
            rating_data_raw = cursor.fetchall()
            if rating_data_raw:
                df_ratings = pd.DataFrame([dict(row) for row in rating_data_raw])
                fig_ratings, ax_ratings = plt.subplots(figsize=(8, 5))
                ax_ratings.bar(df_ratings['rating'], df_ratings['count'], color='skyblue')
                ax_ratings.set_title('전체 영화 평점 분포')
                ax_ratings.set_xlabel('평점')
                ax_ratings.set_ylabel('영화 수')
                ax_ratings.set_xticks(df_ratings['rating'])
                st.pyplot(fig_ratings)
            else:
                st.info("평점 데이터를 기반으로 한 그래프입니다. 아직 평점이 없습니다.")

            st.markdown("---")

            # 2. 장르 선호도 (가장 많이 평가된 영화의 장르 상위 5개)
            cursor.execute("""
                SELECT m.genre, COUNT(r.id) as review_count
                FROM movies m JOIN reviews r ON m.id = r.movie_id
                WHERE m.genre IS NOT NULL AND m.genre != ''
                GROUP BY m.genre
                ORDER BY review_count DESC LIMIT 5
            """)
            genre_data_raw = cursor.fetchall()
            if genre_data_raw:
                df_genres = pd.DataFrame([dict(row) for row in genre_data_raw])
                
                fig_genres, ax_genres = plt.subplots(figsize=(8, 5))
                ax_genres.pie(df_genres['review_count'], labels=df_genres['genre'], autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
                ax_genres.set_title('선호 장르 분석 (가장 많이 평가된 영화)')
                ax_genres.axis('equal') 
                st.pyplot(fig_genres)
            else:
                st.info("장르 데이터를 기반으로 한 그래프입니다. 아직 장르 정보가 부족합니다.")

            st.markdown("---")

            # 3. 연도별 시청 통계
            cursor.execute("""
                SELECT SUBSTR(watch_date, 1, 4) as watch_year, COUNT(*) as movie_count
                FROM reviews
                WHERE watch_date IS NOT NULL
                GROUP BY watch_year
                ORDER BY watch_year ASC
            """)
            watch_data_raw = cursor.fetchall()
            if watch_data_raw:
                df_watches = pd.DataFrame([dict(row) for row in watch_data_raw])
                fig_watches, ax_watches = plt.subplots(figsize=(8, 5))
                ax_watches.plot(df_watches['watch_year'], df_watches['movie_count'], marker='o', color='green')
                ax_watches.set_title('연도별 영화 시청 수')
                ax_watches.set_xlabel('연도')
                ax_watches.set_ylabel('시청 영화 수')
                st.pyplot(fig_watches)
            else:
                st.info("시청 날짜 데이터를 기반으로 한 그래프입니다. 아직 시청 기록이 부족합니다.")

        except sqlite3.Error as err:
            st.error(f"통계 데이터를 불러오는 중 오류 발생: {err}")
        finally:
            cursor.close()
            conn.close()

# --- 앱 시작 시 DB 초기화/확인 ---
init_db()