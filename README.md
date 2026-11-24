# Baseball Buddy
<p>Streamlit application which allows the user to ask natural language questions about MLB hitters. This project 
utilizes Google Gemini to answer these questions using a local database as a knowledge source, with the 'pybaseball' 
library used to populate the database with player statistics.</p>

<p><b>Technologies Used</b></p>
<ul>
    <Li>
        Python 3.11.4
    </Li>
    <li>
        Pybaseball
    </li>
    <li>Pandas</li>
    <li>SQLite</li>
    <li>BCrypt</li>
    <li>Google GenAI SDK</li>
</ul>

<p><b>Features</b></p>
<ul>
    <li>
        Before allowing access, a password gate is implemented (checking against a hashed password) to mitigate API abuse.
    </li>
    <Li>
        Player names are normalized to remove accents, for easier lookup.
    </Li>
    <li>    
        Gemini utilizes a set of predefined tool functions to determine which database lookups to run.
    </li>
    <li>
        Utilizes model fallback, so if one model is unavailable due to rate limits, server overload, etc., the 
        application will move to the next model in the set.
    </li>
</ul>

<p><b>Known Issues/Limitations</b></p>
<ul>
    <Li>
        For now, the database only contains data beginning with the 2020 MLB season.
    </Li>
    <li>
        Due to the Fangraphs API becoming pay-walled, Baseball Reference data is used which has issues with combining
        regular season and postseason statistics for certain players.
    </li>
    <li>
        Baseball buddy is unable to answer questions about MLB pitchers, or Minor League players as that is outside of 
        the application's current scope.
    </li>
</ul>

<p><b>Future Improvements</b></p>
<ul>
    <Li>
        Switch from using pybaseball to the public MLB Stats API to populate the database.
    </Li>
    <li>
        Implement a cooldown for known unavailable models, to limit 429 or 503 responses.
    </li>
    <li>
        Add an 'administrator view', allowing for the admin to refresh the database with current season statistics 
        within the application itself.
    </li>
    <li>
        Add more historical data, in small increments (so the next chunk would be the 2015-2019 seasons).
    </li>
    <li>Add capability for users to clear chat, without having to refresh the application.</li>
</ul>

