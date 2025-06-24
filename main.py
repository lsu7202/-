# main.py
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# ----------------------------------------------------
# 1. Firebase Admin SDK 초기화
# ----------------------------------------------------
# 서비스 계정 키 파일의 경로를 지정합니다.
# 실제 배포 시에는 환경 변수로 관리하는 것이 좋습니다.
SERVICE_ACCOUNT_KEY_PATH = "myapp-dc703-firebase-adminsdk-fbsvc-74be26f983.json"

try:
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK initialized successfully!")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    # 서비스 계정 파일이 없거나 잘못된 경우 앱이 시작되지 않도록 처리할 수 있습니다.
    # 여기서는 예시를 위해 print만 하고 진행하지만, 실제 프로덕션에서는 다르게 처리해야 합니다.

db = firestore.client()

# ----------------------------------------------------
# 2. FastAPI 애플리케이션 정의
# ----------------------------------------------------
app = FastAPI(
    title="FastAPI Firestore 연동 예제",
    description="Firebase Firestore와 FastAPI를 연동하여 데이터를 관리하는 API 예제입니다."
)

# ----------------------------------------------------
# 3. 데이터 모델 정의 (Pydantic)
# ----------------------------------------------------
class Post(BaseModel):
    title: str
    content: str
    author: Optional[str] = "익명"
    created_at: Optional[str] = None # Firestore에서 타임스탬프 처리 예정

class PostOut(Post):
    id: str # Firestore 문서 ID 추가

# ----------------------------------------------------
# 4. API 엔드포인트 구현
# ----------------------------------------------------

@app.get("/")
async def read_root():
    return {"message": "Welcome to FastAPI with Firestore!"}

@app.post("/posts/", response_model=PostOut, status_code=201)
async def create_post(post: Post):
    """
    새 게시글을 생성합니다.
    """
    try:
        # Firestore에 문서 추가 (컬렉션 'posts')
        # add() 메서드는 문서 ID를 Firestore가 자동으로 생성하도록 합니다.
        doc_ref = db.collection("posts").add(post.model_dump(exclude_unset=True, by_alias=True))
        
        # Firestore에서 생성된 문서 ID를 가져옵니다.
        post_id = doc_ref[1].id
        
        # 생성된 문서의 데이터를 다시 읽어와서 반환 (created_at 등 Firestore에서 추가된 값 포함)
        # 실제로는 Firestore에서 생성된 타임스탬프를 바로 포함해서 반환하는 것이 일반적입니다.
        # 이 예제에서는 단순화를 위해 post_id만 추가하여 반환합니다.
        
        # 만약 Firestore에서 추가된 필드(예: 서버 타임스탬프)를 즉시 반환하고 싶다면,
        # doc_ref[1].get()을 사용하여 문서 스냅샷을 가져와야 합니다.
        # post_data = doc_ref[1].get().to_dict()
        # return PostOut(id=post_id, **post_data)

        return PostOut(id=post_id, **post.model_dump()) # Pydantic 모델에 id 추가

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"게시글 생성 중 오류 발생: {e}")

@app.get("/posts/", response_model=List[PostOut])
async def get_all_posts():
    """
    모든 게시글을 조회합니다.
    """
    try:
        posts = []
        docs = db.collection("posts").stream() # 모든 문서 스트림
        for doc in docs:
            # Firestore 문서 데이터를 Python 딕셔너리로 변환
            post_data = doc.to_dict()
            # 문서 ID를 'id' 필드에 추가
            posts.append(PostOut(id=doc.id, **post_data))
        return posts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"게시글 조회 중 오류 발생: {e}")

@app.get("/posts/{post_id}", response_model=PostOut)
async def get_post(post_id: str):
    """
    특정 ID의 게시글을 조회합니다.
    """
    try:
        doc_ref = db.collection("posts").document(post_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        post_data = doc.to_dict()
        return PostOut(id=doc.id, **post_data)
    except HTTPException as e: # 404 에러는 그대로 다시 발생
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"게시글 조회 중 오류 발생: {e}")

@app.put("/posts/{post_id}", response_model=PostOut)
async def update_post(post_id: str, post: Post):
    """
    특정 ID의 게시글을 업데이트합니다.
    """
    try:
        doc_ref = db.collection("posts").document(post_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        # update() 메서드로 부분 업데이트 가능. set() with merge=True도 가능.
        doc_ref.update(post.model_dump(exclude_unset=True, by_alias=True))
        
        # 업데이트된 데이터를 다시 가져와서 반환
        updated_doc = doc_ref.get()
        updated_post_data = updated_doc.to_dict()
        return PostOut(id=updated_doc.id, **updated_post_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"게시글 업데이트 중 오류 발생: {e}")

@app.delete("/posts/{post_id}", status_code=204)
async def delete_post(post_id: str):
    """
    특정 ID의 게시글을 삭제합니다.
    """
    try:
        doc_ref = db.collection("posts").document(post_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        doc_ref.delete()
        return {"message": "게시글이 성공적으로 삭제되었습니다."}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"게시글 삭제 중 오류 발생: {e}")