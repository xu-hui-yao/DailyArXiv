import sys
import time
import pytz
from datetime import datetime

from utils import get_daily_papers_by_keyword_with_retries, generate_table, back_up_files,\
    restore_files, remove_backups, get_daily_date


beijing_timezone = pytz.timezone('Asia/Shanghai')
# NOTE: arXiv API seems to sometimes return an unexpected empty list.
# get current beijing time date in the format of "2021-08-01"
current_date = datetime.now(beijing_timezone).strftime("%Y-%m-%d")
# 初始化最后更新日期
last_update_date = None
# 安全地获取最后更新日期
try:
    with open("README.md", "r") as f:
        for line in f:
            if "Last update:" in line:
                last_update_date = line.split(": ")[1].strip()
                break
except FileNotFoundError:
    print("README.md not found, proceeding with update...")
    last_update_date = None
# 检查是否需要更新
# if last_update_date == current_date:
#     sys.exit("Already updated today!")
# 如果找不到最后更新日期，继续执行更新
if last_update_date is None:
    print("Warning: Last update date not found in README.md. Proceeding with update...")

keywords = [
    # 简单关键词查询
    # "LOD",
    # "3D Gaussian Splatting",
    # "Large-scale",

    # 复杂查询：必须包含"3D Gaussian Splatting"，且包含"LOD"或"Large-scale"中的一个
    {
        'must': ["3D Gaussian Splatting"],
        'any': ["LOD", "large-scale", "on the fly"]
    },

    # 另一个复杂查询示例：必须包含"NeRF"和"3D"，且包含"reconstruction"或"rendering"中的一个
    # {
    #     'must': ["NeRF", "3D"],
    #     'any': ["reconstruction", "rendering"]
    # }
]

max_result = 1000 # maximum query results from arXiv API for each keyword
issues_result = 150 # maximum papers to be included in the issue

# all columns: Title, Authors, Abstract, Link, Tags, Comment, Date
# fixed_columns = ["Title", "Link", "Date"]

column_names = ["Title", "Link", "Abstract", "Date", "Comment"]

back_up_files() # back up README.md and ISSUE_TEMPLATE.md

# write to README.md
f_rm = open("README.md", "w") # file for README.md
f_rm.write("# Daily Papers\n")
f_rm.write("The project automatically fetches the latest papers from arXiv based on keywords.\n\nThe subheadings in the README file represent the search keywords.\n\nOnly the most recent articles for each keyword are retained, up to a maximum of 100 papers.\n\nYou can click the 'Watch' button to receive daily email notifications.\n\nLast update: {0}\n\n".format(current_date))

# write to ISSUE_TEMPLATE.md
f_is = open(".github/ISSUE_TEMPLATE.md", "w") # file for ISSUE_TEMPLATE.md
f_is.write("---\n")
f_is.write("title: Latest {0} Papers - {1}\n".format(issues_result, get_daily_date()))
f_is.write("labels: documentation\n")
f_is.write("---\n")
f_is.write("**Please check the [Github](https://github.com/zezhishao/MTS_Daily_ArXiv) page for a better reading experience and more papers.**\n\n")

for keyword in keywords:
    # 格式化关键词用于标题显示
    if isinstance(keyword, dict):
        title = "Must: " + ", ".join(keyword['must'])
        if keyword.get('any'):
            title += "; Any: " + ", ".join(keyword['any'])
    elif isinstance(keyword, tuple):
        title = "Must: " + ", ".join(keyword[0]) + "; Any: " + ", ".join(keyword[1])
    else:
        title = keyword

    f_rm.write(f"## {title}\n")
    f_is.write(f"## {title}\n")

    # 调用API获取论文（不再需要link参数）
    papers = get_daily_papers_by_keyword_with_retries(keyword, column_names, max_result)
    if papers is None: # failed to get papers
        print("Failed to get papers!")
        f_rm.close()
        f_is.close()
        restore_files()
        sys.exit("Failed to get papers!")
    rm_table = generate_table(papers)
    is_table = generate_table(papers[:issues_result], ignore_keys=["Abstract"])
    f_rm.write(rm_table)
    f_rm.write("\n\n")
    f_is.write(is_table)
    f_is.write("\n\n")
    time.sleep(5) # avoid being blocked by arXiv API

f_rm.close()
f_is.close()
remove_backups()
