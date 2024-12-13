import React, { useContext } from "react";
import assets from "../../assets/assets";
import { Context } from "../../context/Context";

const BottomSection = ({ chatHistory, setChatHistory }) => {
  const {
    response,
    setResponse,
    setShowResult,
    setPreviousPrompt,
    input,
    setInput,
    setRecentPrompt,
    setLoadings,
  } = useContext(Context);

  const handleSend = async (event) => {
    event.preventDefault();
    if (!input) return;

    try {
      setShowResult(true);
      setLoadings(true);
      setRecentPrompt(input);

      // Add user query to chat history
      const loaderIndex = chatHistory.length; // Track loader index
      setChatHistory((prev) => [
        ...prev,
        { type: "user", text: input },
        { type: "bot", text: "", loading: true },
      ]);

      setInput("");
      
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: input,
          provider: "openai", // You can make this dynamic if needed
          model: "gpt-4o-mini", // You can make this dynamic if needed
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to fetch response from the server.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedResponse = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulatedResponse += chunk;

        // Update chat history with the accumulated response
        setChatHistory((prev) =>
          prev.map((chat, index) =>
            index === loaderIndex + 1
              ? { ...chat, text: accumulatedResponse, loading: false }
              : chat
          )
        );
      }

      setResponse(accumulatedResponse);
      setPreviousPrompt((prev) => [...prev, input]);
    } catch (error) {
      console.error("Error:", error);

      const errorMessage = "An error occurred. Please try again.";
      setResponse(errorMessage);

      // Replace loader with error message
      setChatHistory((prev) =>
        prev.map((chat, index) =>
          index === loaderIndex + 1
            ? { ...chat, text: errorMessage, loading: false }
            : chat
        )
      );
    } finally {
      setLoadings(false);
      // setInput(""); // Clear the input field after submission
    }
  };

  return (
    <div className="main-bottom">
      <form className="search-box" onSubmit={handleSend}>
        <input
          type="text"
          placeholder="Ask GenAI Protos anything..."
          onChange={(event) => setInput(event.target.value)}
          value={input}
        />
        <div>
          <img src={assets.mic_icon} alt="Mic" />
          {input ? (
            <button type="submit" style={{ border: "none", background: "none" }}>
              <img src={assets.send_icon} alt="Send" />
            </button>
          ) : null}
        </div>
      </form>
      <p className="bottom-info">
        GenAI Protos may display inaccurate information, such as the number of
        bytes and also including about the people.
      </p>
    </div>
  );
};

export default BottomSection;