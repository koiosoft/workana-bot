import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client.get_database("workana_bot")
    collection = db["projects"]
    
    # Contar proyectos analyzed
    analyzed_count = await collection.count_documents({"proposal_status": "analyzed"})
    print(f"Total analyzed: {analyzed_count}")
    
    # Contar con score >= 5
    analyzed_high_score = await collection.count_documents({
        "proposal_status": "analyzed",
        "ai_score": {"$gte": 5}
    })
    print(f"Total analyzed con ai_score >= 5: {analyzed_high_score}")
    
    # Contar sin full_description
    analyzed_no_desc = await collection.count_documents({
        "proposal_status": "analyzed",
        "full_description": {"$exists": False}
    })
    print(f"Total analyzed SIN full_description: {analyzed_no_desc}")
    
    # Contar que cumplan TODAS las condiciones
    ready = await collection.count_documents({
        "proposal_status": "analyzed",
        "ai_score": {"$gte": 5},
        "full_description": {"$exists": False}
    })
    print(f"Total listos para procesar (analyzed + score>=5 + sin desc): {ready}")
    
    # Ver un sample
    sample = await collection.find_one({"proposal_status": "analyzed"})
    if sample:
        print(f"\nSample project:")
        print(f"  - ai_score: {sample.get('ai_score', 'MISSING')}")
        print(f"  - has full_description: {bool(sample.get('full_description'))}")
        print(f"  - contract_type: {sample.get('contract_type', 'MISSING')}")

if __name__ == "__main__":
    asyncio.run(main())
