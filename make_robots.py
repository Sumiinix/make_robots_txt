import urllib.request
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from textwrap import dedent
import yaml
import logging
import re
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def get_config(file_name):
    try:
        with open(file_name, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None
    except yaml.YAMLError as exc:
        logger.error(f"YAML Error:\n{exc}")
        quit()

def is_local(url_parse):
    if url_parse.scheme in ('file', ''):
        return True
    return False

def get_file_with_url(url):
    try:
        response = urllib.request.urlopen(url)
    except HTTPError as error:
        logger.error(f"Couldn't get file\n<{error}>")
        quit()
    except URLError as error:
        logger.error(dedent(f"""\
        URLError
        {error}
        <Is the URL accessible?>
        """))
        quit()
    byte_text = response.read()
    return byte_text.decode().splitlines(keepends=True)

def get_file_from_local(source):
    try:
        with open(source, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError as error:
        logger.error(f"File Not Found\n{error}")
        quit()
    return lines

def if_agent_line(line):
    return re.match("User-agent:", line, flags=re.IGNORECASE)

def extract_user_agent(line):
    if line.lower().startswith("user-agent:"):
        return line.split(":", 1)[1].strip()

def parse_robots_blocks(lines):
    blocks = []
    block = []
    
    seen_agents = set()

    new_rule = False
    agent_line = False

    for line in lines:
        if line:
            if if_agent_line(line):
                if new_rule:
                    if agent_line:
                        blocks.extend(block + [""])
                    block = []
                    new_rule = False
                    agent_line = False

                re.sub("user-agent:", "User-agent:", line, flags=re.IGNORECASE)
                
                agent = extract_user_agent(line)
                
                if agent in seen_agents:
                    logger.debug(f"User-agent: {agent} is duplicated.")
                    continue

                seen_agents.add(agent)
                block.append(line)
                agent_line = True
                
            elif re.match("Disallow:", line, flags=re.IGNORECASE):
                re.sub("disallow:", "Disallow:", line, flags=re.IGNORECASE)
                block.append(line)
                new_rule = True
            elif re.match("Allow:", line, flags=re.IGNORECASE):
                re.sub("allow:", "Allow:", line, flags=re.IGNORECASE)
                block.append(line)
                new_rule = True

    if block and agent_line:
        blocks.extend(block)

    return blocks

def generate_robots(outputs, lines):
    for i, output in enumerate(outputs, start=1):
        logger.debug(f"Saving file {i} : {output}.")
        output_dir = os.path.dirname(output)
        os.makedirs(output_dir, exist_ok=True)
        with open(output, 'w') as f:
            f.write('\n'.join(lines))

def strip_robots_text(robots_text):
    robots_text[:] = [line.strip() for line in robots_text]

if (config := get_config("config.yaml")) == None:
    if config := get_config("config.yml") == None:
        logger.error("No config file")
        quit()

robots_text_list = []

for key, value in config.items():
    logger.info(f"Making robots.txt for {key}.")
    
    sources = value.get("source")
    outputs = value.get("output")

    for i, source in enumerate(sources, start=1):
        logger.debug(f"Parsing source {i} : {source}.")
        
        # Parse URL
        if re.match("^//(?!/)", source):
            source = f"http:{source}"
            logger.debug("Scheme added. \"http:\".")
            logger.debug(f"Source updated to: {source}.")

        url_parse = urlparse(source)
        
        # Get file
        if is_local(url_parse):
            logger.debug("Getting file from local...")
            robots_text = get_file_from_local(source)
            #logger.debug(f"robots.txt fetched\n{''.join(robots_text)}")
            logger.debug(f"robots.txt fetched.")
        else:
            logger.debug("Getting file from URL...")
            url = url_parse.geturl()
            robots_text = get_file_with_url(url)
            #logger.debug(f"robots.txt fetched\n{''.join(robots_text)}")
            logger.debug(f"robots.txt fetched.")

        strip_robots_text(robots_text)
        
        # Find User-Agent
        l = len(robots_text) - 1
        for j, line in enumerate(robots_text):
            if re.search("user-agent:", line, flags=re.IGNORECASE):
                logger.debug("User-Agent rules found")
                break
            else:
                if j < l:
                    logger.error("User-Agent rules not found")
                    quit()
        
        # Add to list
        robots_text_list.extend(robots_text)
        logger.debug(f"Successfully loaded Source {i} from {source}")

    # Remove dupe agent
    logger.debug(f"Checking for duplicates...")
    robots_text_list = parse_robots_blocks(robots_text_list)
    logger.debug(f"Finished checking for duplicates.")

    # Save file
    generate_robots(outputs, robots_text_list)
    
    logger.info(f"Finished creating robots.txt for {key}.")
