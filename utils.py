import os
import time
import pytz
import shutil
import datetime
from typing import List, Dict
import urllib, urllib.request

import feedparser
from easydict import EasyDict


def remove_duplicated_spaces(text: str) -> str:
    return " ".join(text.split())

def request_paper_with_arXiv_api(keyword: str, max_results: int) -> List[Dict[str, str]]:
    """
        修改后的函数，支持多种关键词格式：
        1. 字符串：单个关键词
        2. 元组：(must_terms, any_terms) - 必须出现的术语和可选术语
        3. 字典：{'must': [...], 'any': [...]} - 必须出现的术语和可选术语
        """
    # 构建查询语句
    if isinstance(keyword, str):
        # 单个关键词查询
        if " " in keyword:
            query = f'abs:"{keyword}"'
        else:
            query = f'abs:{keyword}'
    elif isinstance(keyword, (tuple, list)) and len(keyword) == 2:
        # 元组格式：(must_terms, any_terms)
        must_terms, any_terms = keyword
        query = build_complex_query(must_terms, any_terms)
    elif isinstance(keyword, dict):
        # 字典格式：{'must': [...], 'any': [...]}
        must_terms = keyword.get('must', [])
        any_terms = keyword.get('any', [])
        query = build_complex_query(must_terms, any_terms)
    else:
        raise ValueError("Unsupported keyword format. Use str, tuple, or dict.")

    # 构建 URL
    base_url = "http://export.arxiv.org/api/query?"
    params = {
        "search_query": query,
        "max_results": max_results,
        "sortBy": "lastUpdatedDate"
    }
    url = base_url + urllib.parse.urlencode(params)

    # 发送请求并解析
    response = urllib.request.urlopen(url).read().decode('utf-8')
    feed = feedparser.parse(response)
    # 解析结果（保持不变）
    papers = []
    for entry in feed.entries:
        entry = EasyDict(entry)
        paper = EasyDict()

        # title
        paper.Title = remove_duplicated_spaces(entry.title.replace("\n", " "))
        # abstract
        paper.Abstract = remove_duplicated_spaces(entry.summary.replace("\n", " "))
        # authors
        paper.Authors = [remove_duplicated_spaces(_["name"].replace("\n", " ")) for _ in entry.authors]
        # link
        paper.Link = remove_duplicated_spaces(entry.link.replace("\n", " "))
        # tags
        paper.Tags = [remove_duplicated_spaces(_["term"].replace("\n", " ")) for _ in entry.tags]
        # comment
        paper.Comment = remove_duplicated_spaces(entry.get("arxiv_comment", "").replace("\n", " "))
        # date
        paper.Date = entry.updated

        papers.append(paper)
    return papers


def build_complex_query(must_terms: list, any_terms: list) -> str:
    """构建复杂查询语句"""
    query_parts = []

    # 处理必须出现的术语
    for term in must_terms:
        if " " in term:
            query_parts.append(f'abs:"{term}"')
        else:
            query_parts.append(f'abs:{term}')

    # 处理可选出现的术语
    if any_terms:
        any_query = []
        for term in any_terms:
            if " " in term:
                any_query.append(f'abs:"{term}"')
            else:
                any_query.append(f'abs:{term}')
        query_parts.append("(" + " OR ".join(any_query) + ")")

    # 组合完整查询
    return " AND ".join(query_parts)


def filter_tags(papers: List[Dict[str, str]], target_fileds: List[str]=["cs", "stat"]) -> List[Dict[str, str]]:
    # filtering tags: only keep the papers in target_fileds
    results = []
    for paper in papers:
        tags = paper.Tags
        for tag in tags:
            if tag.split(".")[0] in target_fileds:
                results.append(paper)
                break
    return results

def get_daily_papers_by_keyword_with_retries(keyword, column_names: List[str], max_result: int, retries: int = 6) -> List[Dict[str, str]]:
    for _ in range(retries):
        papers = get_daily_papers_by_keyword(keyword, column_names, max_result)
        if len(papers) > 0:
            return papers
        print("Unexpected empty list, retrying...")
    return None

def get_daily_papers_by_keyword(keyword, column_names: List[str], max_result: int) -> List[Dict[str, str]]:
    papers = request_paper_with_arXiv_api(keyword, max_result)
    papers = filter_tags(papers)
    papers = [{column_name: paper[column_name] for column_name in column_names} for paper in papers]
    return papers

def generate_table(papers: List[Dict[str, str]], ignore_keys: List[str] = []) -> str:
    formatted_papers = []
    keys = papers[0].keys()
    for paper in papers:
        # process fixed columns
        formatted_paper = EasyDict()
        ## Title and Link
        formatted_paper.Title = "**" + "[{0}]({1})".format(paper["Title"], paper["Link"]) + "**"
        ## Process Date (format: 2021-08-01T00:00:00Z -> 2021-08-01)
        formatted_paper.Date = paper["Date"].split("T")[0]
        
        # process other columns
        for key in keys:
            if key in ["Title", "Link", "Date"] or key in ignore_keys:
                continue
            elif key == "Abstract":
                # add show/hide button for abstract
                formatted_paper[key] = "<details><summary>Show</summary><p>{0}</p></details>".format(paper[key])
            elif key == "Authors":
                # NOTE only use the first author
                formatted_paper[key] = paper[key][0] + " et al."
            elif key == "Tags":
                tags = ", ".join(paper[key])
                if len(tags) > 10:
                    formatted_paper[key] = "<details><summary>{0}...</summary><p>{1}</p></details>".format(tags[:5], tags)
                else:
                    formatted_paper[key] = tags
            elif key == "Comment":
                if paper[key] == "":
                    formatted_paper[key] = ""
                elif len(paper[key]) > 20:
                    formatted_paper[key] = "<details><summary>{0}...</summary><p>{1}</p></details>".format(paper[key][:5], paper[key])
                else:
                    formatted_paper[key] = paper[key]
        formatted_papers.append(formatted_paper)

    # generate header
    columns = formatted_papers[0].keys()
    # highlight headers
    columns = ["**" + column + "**" for column in columns]
    header = "| " + " | ".join(columns) + " |"
    header = header + "\n" + "| " + " | ".join(["---"] * len(formatted_papers[0].keys())) + " |"
    # generate the body
    body = ""
    for paper in formatted_papers:
        body += "\n| " + " | ".join(paper.values()) + " |"
    return header + body

def back_up_files():
    # back up README.md and ISSUE_TEMPLATE.md
    shutil.move("README.md", "README.md.bk")
    shutil.move(".github/ISSUE_TEMPLATE.md", ".github/ISSUE_TEMPLATE.md.bk")

def restore_files():
    # restore README.md and ISSUE_TEMPLATE.md
    shutil.move("README.md.bk", "README.md")
    shutil.move(".github/ISSUE_TEMPLATE.md.bk", ".github/ISSUE_TEMPLATE.md")

def remove_backups():
    # remove README.md and ISSUE_TEMPLATE.md
    os.remove("README.md.bk")
    os.remove(".github/ISSUE_TEMPLATE.md.bk")

def get_daily_date():
    # get beijing time in the format of "March 1, 2021"
    beijing_timezone = pytz.timezone('Asia/Shanghai')
    today = datetime.datetime.now(beijing_timezone)
    return today.strftime("%B %d, %Y")
