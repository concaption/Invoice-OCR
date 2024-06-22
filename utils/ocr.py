from typing import Optional
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from utils.schema import Shipment


load_dotenv()

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are an OCR tool that can extract structured data from Bills of Lading (BOLs). Extract the data from the BOL below. Return None if any data is missing."),
        (
            "user",
            [{"type": "image_url", "image_url": "data:image/jpeg;base64,{image_data}"}],
        ),
    ]
)

model = ChatOpenAI(model="gpt-4o")
llm = model.with_structured_output(Shipment)

runnable = prompt | llm

class OCRTool:
    def __init__(self):
        self.runnable = runnable

    def run(self, image_data: str) -> Optional[Shipment]:
        try:
            response = self.runnable.invoke({"image_data": image_data})
            result = response.dict()
            return result
        except Exception as e:
            print(e)
            return None