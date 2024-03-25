import os
import logging

#keep this config here, otherwise logging setup is overwritten
log_path = '/var/log/tt/publisher.log'
os.makedirs(os.path.dirname(log_path), exist_ok=True)
logging.basicConfig(filename=log_path, level=logging.INFO,
                format='%(asctime)s:%(levelname)s:%(message)s')

import time
import re
import json
import traceback
import random
import html

from jinja2 import Template
from bs4 import BeautifulSoup

from browser import fetch_content
from llm import fetch_llm_response
from templater import deploy_website, deploy_games

def publish(sources_filename, template_filename, html_filename, **kwargs):        

    locals().update(**kwargs)

    with open(sources_filename, 'r') as file:
        sources_config = json.load(file)

    random.shuffle(sources_config)

    article_dict = {}

    for source_config in sources_config:
        try:
            locals().update(source_config)
            parser = parser or "text"
            finder_model = finder_model or "Open Mixtral"
            summarizer_model = summarizer_model or "Open Mixtral"

            #as a rule, we don't publish same-language summaries
            if source_language == publishing_language:
                continue

            all_links = fetch_content(url,"links",language) 
            
            logging.info(name)

            best_links = fetch_llm_response(
                all_links, finder_template.render(**locals()),
                finder_model, "url")
            
            logging.info(best_links)
            
            #we are only expecting one link, slice the list to just select the first item
            link = best_links[0]
            #sometimes the llm shares the link like "here's the link https://example.com/article."
            #periods are valid at the end of links, but this almost never happens in practice
            #so we remove the period here
            if link.endswith('.'):
                link = link[:-1]

            article_text = fetch_content(link, parser, language)

            article_summary = fetch_llm_response(
                    article_text, summarizer_template.render(**locals()),
                    summarizer_model, "html-article")
            
            # Save the title
            soup = BeautifulSoup(article_summary, 'html.parser')
            title_div = soup.find('div', class_='article-title')
            article_title=title_div.text.strip()
           
            if title_div:
                flag_span = soup.new_tag('span', attrs={'role': 'img', 'aria-label': f'Flag of {name}'})
                flag_span.string = html.unescape(flag)
                title_div.insert(0, flag_span)
                title_div.insert(1, ' ')

            content_div = soup.find('div', class_='article-content')

            if content_div:
                link = soup.new_tag('a', href=link)
                link.string = f'Read more from {source} (in {language}).'
                content_div.append(' ')
                content_div.append(link)

            title_div = soup.find('div', class_='article-title')

            if title_div:
                title_div['onclick'] = 'toggleArticleDetails(this)'
                                
            article_summary = str(soup)

            # Get the front page score
            article = soup.find('div', class_='article')
            front_page_score = float(article['data-front-page-score'])
            
            article_dict[article_title] = {}
            article_dict[article_title]["html"] = article_summary
            article_dict[article_title]["score"] = front_page_score
            
            logging.info(article_summary)
        except Exception as e:
            logging.exception(f"An unexpected error occurred, ignoring: {e}")
            traceback.print_exc()
    
    sorted_articles = sorted(article_dict.items(), key=lambda x: x[1]['score'], reverse=True)
    article_html=""
    for article_title, article_data in sorted_articles:
        if article_data['score'] > 2:
            article_html += article_data['html']

    complete_html = deploy_website(article_html, template_filename, html_filename, **locals())
    logging.info(complete_html)


def load_template(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return Template(file.read())


def get_language_config(language):
    with open('config/languages.json', 'r') as file:
        lang_configs = json.load(file)
    
    for item in lang_configs:
        if item.get("name") == language:
            return item
    return None


def deploy_language(publishing_language):
    lang_config = get_language_config(publishing_language)

    locals().update(lang_config)

    finder_template = load_template('config/finder.txt')
    summarizer_template = load_template('config/summarizer.txt')
    
    debug = os.environ.get('DEBUG', False)
    config_file = 'config/sources_debug.json' if debug else 'config/sources.json'
   
    publish(config_file,\
            'template.html',\
            f'{publishing_language_short}.html',\
            **locals())

    # Create the finance and technology page
    if not debug:
        persona = finance_technology_persona
        publish('config/sources_finance_technology.json',\
                'template.html',\
                f'{publishing_language_short}-ft.html',\
                **locals())

if __name__ == "__main__":
    #TODO get which language to publish from an ENV variable
    deploy_language("English")
