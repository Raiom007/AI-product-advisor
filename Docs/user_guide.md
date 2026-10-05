# User Guide

Welcome to the AI Product Advisor! This interface is designed to help you find exactly what you're looking for, understand *why* it was recommended, and inspect the underlying decisions our AI agent makes behind the scenes.

## 1. Chat
This is the main interaction hub.
- **Search Bar**: Describe what you need in natural language (e.g., "40 hazaar tak ka laptop for video editing"). The system supports Hinglish and understands soft preferences vs. hard constraints.
- **Results**: You will see ranked product cards. Each card displays:
  - **Key Specs**: Extracted specifications that explicitly meet your requirements.
  - **Explanation**: A grounded summary explaining why this product is a good fit.
  - **Review Quotes**: Direct quotes from real users, complete with their ratings and dates.
  - **Score Breakdown**: Click the expander to see the mathematical weights and signals (like relevance, sentiment, and trust) that placed this product at its specific rank.

## 2. Trace Viewer
Ever wonder what the AI is thinking? The Trace tab gives you full transparency.
- **Plan Graph**: See the step-by-step tool execution path the agent took (e.g., parsing -> retrieval -> review analysis -> vision -> ranking).
- **Execution Log**: Inspect every API call, retry, fallback, and verification step.
- **Budget Report**: View the real-time latency and API usage to ensure the system is staying within its strict budgets.

## 3. Fake-Review Inspector
Our system automatically identifies and penalizes fake or low-quality reviews before they influence recommendations.
- Use this screen to search for a specific product and see which of its reviews were flagged.
- **Signals**: See exactly *why* a review was flagged (e.g., "burst", "near_duplicate", "extreme_sentiment").
- **Action**: Check whether the review was fully `excluded` from the pool or simply `downweighted`.
