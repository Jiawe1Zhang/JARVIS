Here are some examples of how to decompose instructions into hybrid search queries:

Example 1:
User Instruction: "Jarvis 是一个刚入学ZJU的医学系的学生, Jarvis想要统计今年他们医学院的录取情况, 顺便通过分析来自和他同专业同学B的高考故事来分析他后面同学B的竞争情况!你的分析要简短简洁but必须分析得有道理, 把他对在ZJU和同学B学习竞争情况的分析保存到{output_path}/zjuanalysisqueryrewriteB.md, 输出一个漂亮md文件"
Output: [
    "Jarvis是医学系学生", 
    "ZJU医学系录取情况", 
    "医学专业同学B的高考故事", 
    "Jarvis 的高考分数和院系信息"
]

Example 2:
User Instruction: "Research the differences between BERT and GPT-4 models, specifically regarding attention mechanisms."
Output: [
    "BERT vs GPT-4",
    "attention mechanism comparison",
    "What are the differences in attention mechanisms between BERT and GPT-4?",
    "BERT GPT-4 architecture comparison"
]

Example 3:
User Instruction: "Find the error logs related to the database connection timeout yesterday."
Output: [
    "database connection timeout",
    "error logs yesterday",
    "database timeout logs",
    "Show me the error logs for database connection timeouts from yesterday"
]

----------------
Current User Instruction: "{original_task}"

Please generate {num_queries} hybrid search queries (keywords + phrases + sentences) following the examples above.
Output JSON directly:
