Bhuvan Prashanth and Andrei Saramukov -- University High School -- 6/29/25 -- Category: Health and Wellness -- Project Name: MedSense -- Description: A telegram and whatsapp bot that helps users with low connectivity and users that speak a variety of languages diagnose themselves with the help of Gemini and PubMed (a medical database). 


# MedSense Bot
The first medical bot to access real-time medical data from the web, and provide support to the user without requiring a frontend. 

## Workflow: 
 1. A set of webhooks for Telegram, Whatsapp
 2. A LangGraph agent that processes user requests, creates user profiles for them
 3. The agent posesses several tools MEDICAL_TOOLS = [
    web_search_medical, - searches pubmed
    find_nearby_hospitals, - finds hospitals nearby, given a location
    get_user_profile_tool, - retrieves the user's profile
    save_user_profile_tool, - saves the user profile
    check_disease_outbreaks, - checks for disease outbreaks in the user's region
    final_diagnosis, - saves a presumed diagnosis into a database
    search_medical_database, - deprecated (no longer works)
] 
 4. After the tools are called, the agent processes them and returns the response to the user.

The agent is capable of calling tools iteratively, for an indefinite ammount of times, as long as needed. That allows for more depth in research, and user information handling. 

 #### The agent utilizes PubMed API for efficient research. Later, from the provided articles, it constucts the most probable diagnosis, and gives its recommendations to the user.

 The links to all resources and articles are used in the process of writing the response and developing a probable diagnosis. 

 #### The model supports multimodal inputs
This means that the agent will infer information not only from the text you provide, but also from the image attachments.

## Extra Features
1. Every 24 hours after the user has reported symptoms, the agent checks back on the user, and asks them whether they are doing well.
2. If location is provided by the user, the agent will find the nearest medical facilities, and also determine whether there are any disease outbreaks in the area, that the user should be aware of.
3. The agent keep track of your symptoms and your profile, in order to provide help in an orderly manner.

## APIs that are used
1. Gemini API
2. PubMed API
3. Telegram Webhooks
4. WhatsApp webhooks
5. OpenStreetMap/Nominatim API

 ## Disclaimer
 This bot does not replace real medical health, and is not a doctor, it is AI. This message is prominently displayed in every interaction.
