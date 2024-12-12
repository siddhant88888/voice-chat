import os
import shutil
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import UnstructuredAPIFileLoader
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.prompts import ChatPromptTemplate
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Adjust this to match your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to store initialized LLM and embeddings
initialized_llm = None
initialized_embeddings = None
unstructured_api_key = None

async def generate_document_queries(
    document_content: str, num_queries: int = 4
) -> List[str]:
    global initialized_llm
    
    if not initialized_llm:
        raise ValueError("LLM not initialized. Please call /initialize first.")
    
    system_prompt = f"""
    Generate {num_queries} different questions that could be asked about the following document content:
    Analyze the document content properly before generating questions.
    Generate unique questions about this doc which will lure users to interact with it.
    Based on the context create personalized questions.

    Response Rules:
        1. Each question should be on a new line.
        2. Do not include any comments or instructions in the response.
        3. Do not include any numbers, bullet points, or special characters in the response.
        4. Questions should be relevant to the document content provided and very short and concise to the point.
    
    {document_content}
    """

    prompt = system_prompt
    response = initialized_llm.invoke(prompt)

    queries = response.content.split("\n")

    # Filter out any empty strings from the split
    return [query.strip() for query in queries if query.strip()]

@app.get("/")
async def root():
    return JSONResponse(
        content={"message": "Proto AI"}, status_code=200
    )

@app.post("/initialize")
async def initialize_llm(data: Dict[str, str]):
    """
    Endpoint for initializing the LLM and embeddings with provided API keys.
    """
    global initialized_llm, initialized_embeddings, unstructured_api_key
    
    model = data.get("model", "gpt-4o-mini")
    api_key = data.get("api_key")
    unstructured_api_key = data.get("unstructured_api_key")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")
    
    if not unstructured_api_key:
        raise HTTPException(status_code=400, detail="Unstructured API key is required")
    
    try:
        initialized_llm = ChatOpenAI(api_key=api_key, model=model, streaming=True)
        initialized_embeddings = OpenAIEmbeddings(api_key=api_key, model="text-embedding-3-small")
        
        return JSONResponse(
            content={"message": "LLM and embeddings initialized successfully with OpenAI"},
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error initializing LLM and embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error initializing LLM and embeddings: {str(e)}")

@app.post("/upload")
async def upload_file(user_id: str, file: UploadFile = File(...)):
    """
    Endpoint for uploading a PowerPoint file.
    Returns the file path of the uploaded file.
    """
    if not file.filename.endswith('.pptx'):
        raise HTTPException(status_code=400, detail="Only .pptx files are allowed")
    
    # Save the uploaded file
    user_upload_dir = f"uploads/{user_id}"
    os.makedirs(user_upload_dir, exist_ok=True)
    file_path = f"{user_upload_dir}/{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    logging.info(f"File uploaded for user {user_id}: {file_path}")
    
    return JSONResponse(
        content={
            "message": "File uploaded successfully",
            "file_path": file_path
        },
        status_code=200
    )

@app.post("/embed")
async def embed_file(data: Dict[str, str]):
    """
    Endpoint for embedding the content of a PowerPoint file.
    Creates and saves a FAISS vector store for a specific user.
    """
    global initialized_llm, initialized_embeddings, unstructured_api_key
    
    if not initialized_llm or not initialized_embeddings:
        raise HTTPException(status_code=400, detail="LLM and embeddings not initialized. Please call /initialize first.")
    
    file_path = data.get("file_path")
    user_id = data.get("user_id")
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not file_path.endswith('.pptx'):
        raise HTTPException(status_code=400, detail="Only .pptx files are allowed")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    
    try:
        loader = UnstructuredAPIFileLoader(
            api_key=unstructured_api_key,
            file_path=file_path,
            mode="elements",
            strategy="fast",
            url="https://api.unstructuredapp.io/general/v0/general"
        )
        data = loader.load()
        logging.info(f"Data loaded for user {user_id}. Number of documents: {len(data)}")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=10)
        split_data = text_splitter.split_documents(data)
        logging.info(f"Documents split for user {user_id}. Number of chunks: {len(split_data)}")

        vectorstore = FAISS.from_documents(split_data, initialized_embeddings)
        
        # Save the vectorstore for the specific user
        vectorstore_path = f"vectorstore/{user_id}"
        os.makedirs(vectorstore_path, exist_ok=True)
        vectorstore.save_local(vectorstore_path)
        logging.info(f"FAISS vector store created and saved successfully for user {user_id}")

        queries = await generate_document_queries(str(data))
        
        return JSONResponse(
            content={
                "message": "Document embedded successfully",
                "queries": queries
            },
            status_code=200,
        )
    except Exception as e:
        logging.error(f"Error processing file for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/chat")
async def chat(data: Dict[str, Any]):
    """
    Endpoint for chatting with the AI about the embedded PowerPoint content.
    Uses a persistent FAISS vector store for retrieval specific to a user.
    """
    global initialized_llm, initialized_embeddings
    
    if not initialized_llm or not initialized_embeddings:
        raise HTTPException(status_code=400, detail="LLM and embeddings not initialized. Please call /initialize first.")
    
    question = data.get("question", "")
    user_id = data.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    
    vectorstore_path = f"vectorstore/{user_id}"
    if not os.path.exists(vectorstore_path):
        raise HTTPException(status_code=400, detail=f"No document has been embedded for user {user_id}")

    async def generate_response():
        try:
            try:
                vectorstore = FAISS.load_local(vectorstore_path, initialized_embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                logging.error(f"Error loading vector store for user {user_id}: {str(e)}")
                yield f"Error: Unable to load the vector store. Please try embedding the document again."
                return

            retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
            
            prompt = ChatPromptTemplate.from_template(
                """You are an AI assistant specialized in analyzing PowerPoint presentations. Your role is to help users understand and extract information from their presentations in a conversational way.

Given the following presentation content, please provide a clear and concise response to the user's question. If the information is not directly available in the context, say so instead of making assumptions.

Context from the presentation:
{context}

answer only from provided context and do not fabricate information

User's Question: {input}

Response: """
            )

            document_chain = create_stuff_documents_chain(initialized_llm, prompt)
            retrieval_chain = create_retrieval_chain(retriever, document_chain)
            logging.info(f"Retrieval chain created for user {user_id}")

            response = retrieval_chain.astream({"input": question})
            async for chunk in response:
                if "answer" in chunk:
                    yield chunk["answer"]
        except Exception as e:
            logging.error(f"Error during chat for user {user_id}: {str(e)}")
            yield f"Error: {str(e)}"

    return StreamingResponse(generate_response(), media_type="text/plain")

@app.delete("/delete_vectorstore/{user_id}")
async def delete_vectorstore(user_id: str):
    """
    Endpoint to delete the vectorstore for a specific user.
    """
    vectorstore_path = f"vectorstore/{user_id}"
    if not os.path.exists(vectorstore_path):
        raise HTTPException(status_code=404, detail=f"No vectorstore found for user {user_id}")
    
    try:
        shutil.rmtree(vectorstore_path)
        logging.info(f"Vectorstore deleted for user {user_id}")
        return JSONResponse(
            content={"message": f"Vectorstore deleted successfully for user {user_id}"},
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error deleting vectorstore for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting vectorstore: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("fastapi_ppt_chat:app", host="localhost", port=8000, reload=True)

# uvicorn fastapi_ppt_chat:app --host localhost --port 8000 --reload
