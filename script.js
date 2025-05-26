document.addEventListener('DOMContentLoaded', () => {
    const ELO_K_FACTOR = 32; // Should ideally match config.py if it were accessible here
    const ELO_DEFAULT_RATING = 1500; // Should ideally match config.py

    const eloTableBody = document.getElementById('elo-table-body');
    const battleListUl = document.getElementById('battle-list');
    const battleDetailsContentDiv = document.getElementById('battle-details-content');

    async function fetchData() {
        try {
            const response = await fetch('data.json');
            if (!response.ok) {
                // If data.json doesn't exist (e.g., first run), handle gracefully
                if (response.status === 404) {
                    console.warn('data.json not found. Displaying empty state.');
                    return []; 
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const battles = await response.json();
            return battles;
        } catch (error) {
            console.error("Could not fetch or parse data.json:", error);
            battleDetailsContentDiv.innerHTML = `<p>Error loading battle data. Please ensure 'data.json' exists and is valid. Run the Python backend to generate data.</p>`;
            return []; // Return empty array on error
        }
    }

    function calculateElo(battles) {
        const eloScores = {}; // modelName: { rating: number, battlesPlayed: number }
        const modelNames = new Set();

        // Initialize models from battles
        battles.forEach(battle => {
            modelNames.add(battle.model_A_info.name);
            modelNames.add(battle.model_B_info.name);
        });

        modelNames.forEach(name => {
            eloScores[name] = { rating: ELO_DEFAULT_RATING, battlesPlayed: 0 };
        });

        // Sort battles by timestamp_start to process in chronological order
        battles.sort((a, b) => new Date(a.timestamp_start) - new Date(b.timestamp_start));

        battles.forEach(battle => {
            const modelA = battle.model_A_info.name;
            const modelB = battle.model_B_info.name;

            // Ensure models are in eloScores (should be, due to pre-initialization)
            if (!eloScores[modelA]) eloScores[modelA] = { rating: ELO_DEFAULT_RATING, battlesPlayed: 0 };
            if (!eloScores[modelB]) eloScores[modelB] = { rating: ELO_DEFAULT_RATING, battlesPlayed: 0 };

            const ratingA = eloScores[modelA].rating;
            const ratingB = eloScores[modelB].rating;

            const expectedA = 1 / (1 + Math.pow(10, (ratingB - ratingA) / 400));
            const expectedB = 1 / (1 + Math.pow(10, (ratingA - ratingB) / 400));

            let scoreA, scoreB;

            if (battle.battle_outcome === `${modelA}_wins`) {
                scoreA = 1;
                scoreB = 0;
            } else if (battle.battle_outcome === `${modelB}_wins`) {
                scoreA = 0;
                scoreB = 1;
            } else { // Tie
                scoreA = 0.5;
                scoreB = 0.5;
            }

            eloScores[modelA].rating += ELO_K_FACTOR * (scoreA - expectedA);
            eloScores[modelB].rating += ELO_K_FACTOR * (scoreB - expectedB);
            
            eloScores[modelA].battlesPlayed++;
            eloScores[modelB].battlesPlayed++;
        });
        return eloScores;
    }

    function displayEloTable(eloScores) {
        if (!eloTableBody) return;
        eloTableBody.innerHTML = ''; // Clear existing rows

        const sortedModels = Object.entries(eloScores)
            .sort(([, a], [, b]) => b.rating - a.rating); // Sort by ELO descending

        sortedModels.forEach(([name, data], index) => {
            const row = eloTableBody.insertRow();
            row.insertCell().textContent = index + 1; // Rank
            row.insertCell().textContent = name;
            row.insertCell().textContent = Math.round(data.rating);
            row.insertCell().textContent = data.battlesPlayed;
        });
        if (sortedModels.length === 0) {
            const row = eloTableBody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 4;
            cell.textContent = "No ELO data available. Run battles to generate scores.";
            cell.style.textAlign = "center";
        }
    }

    function displayBattleList(battles, allBattlesData) {
        if (!battleListUl) return;
        battleListUl.innerHTML = ''; // Clear existing list

        // Display latest battles first
        const sortedBattles = [...battles].sort((a, b) => new Date(b.timestamp_start) - new Date(a.timestamp_start));

        sortedBattles.forEach(battle => {
            const li = document.createElement('li');
            li.textContent = `Battle ID: ${battle.battle_id} (${battle.model_A_info.name} vs ${battle.model_B_info.name}) - Outcome: ${battle.battle_outcome || 'N/A'}`;
            li.dataset.battleId = battle.battle_id;
            li.addEventListener('click', () => displayBattleDetails(battle.battle_id, allBattlesData));
            battleListUl.appendChild(li);
        });
         if (sortedBattles.length === 0) {
            const li = document.createElement('li');
            li.textContent = "No battles recorded yet.";
            battleListUl.appendChild(li);
        }
    }

    function escapeHtml(str) {
        return (str + "").replace(/[&<>"']/g, match => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[match]));
    }


    function displayBattleDetails(battleId, battles) {
        if (!battleDetailsContentDiv) return;
        const battle = battles.find(b => b.battle_id === battleId);
        if (!battle) {
            battleDetailsContentDiv.innerHTML = '<p>Battle not found.</p>';
            return;
        }

        let detailsHtml = `<h3>Battle: ${escapeHtml(battle.battle_id)}</h3>`;
        detailsHtml += `<p><strong>Timestamp:</strong> ${new Date(battle.timestamp_start).toLocaleString()} - ${new Date(battle.timestamp_end).toLocaleString()}</p>`;
        detailsHtml += `<p><strong>Model A:</strong> ${escapeHtml(battle.model_A_info.name)}</p>`;
        detailsHtml += `<p><strong>Model B:</strong> ${escapeHtml(battle.model_B_info.name)}</p>`;
        detailsHtml += `<p><strong>Plaintext Color:</strong> <span style="background-color:#${escapeHtml(battle.plaintext_color)}; padding: 2px 5px; border: 1px solid #ccc;">#${escapeHtml(battle.plaintext_color)}</span> (${escapeHtml(battle.plaintext_color)})</p>`;
        detailsHtml += `<p><strong>Overall Outcome:</strong> ${escapeHtml(battle.battle_outcome)}</p>`;

        battle.rounds.forEach(round => {
            detailsHtml += `<div class="round-details">`;
            detailsHtml += `<h4>Round ${round.round_number}</h4>`;
            detailsHtml += `<p>Obfuscator/Deobfuscator (LLM1/2): ${escapeHtml(round.obfuscator_model)}</p>`;
            detailsHtml += `<p>Attacker (LLM3): ${escapeHtml(round.attacker_model)}</p>`;
            
            if (round.llm1_conversation) {
                detailsHtml += `<div class="llm-conversation"><strong>LLM1 (Obfuscator) Conversation:</strong>`;
                detailsHtml += `<p>Prompt:</p><pre>${escapeHtml(round.llm1_conversation.prompt)}</pre>`;
                detailsHtml += `<p>Response:</p><pre>${escapeHtml(round.llm1_conversation.response)}</pre>`;
                detailsHtml += `<p>Parsed Obfuscated Text:</p><pre>${escapeHtml(round.llm1_conversation.parsed_obfuscated_text)}</pre>`;
                detailsHtml += `<p>Parsed Instructions:</p><pre>${escapeHtml(round.llm1_conversation.parsed_instructions)}</pre>`;
                detailsHtml += `</div>`;
            }

            if (round.llm2_conversation) {
                detailsHtml += `<div class="llm-conversation"><strong>LLM2 (Deobfuscator Ally) Conversation:</strong>`;
                detailsHtml += `<p>Prompt:</p><pre>${escapeHtml(round.llm2_conversation.prompt)}</pre>`;
                detailsHtml += `<p>Response:</p><pre>${escapeHtml(round.llm2_conversation.response)}</pre>`;
                detailsHtml += `<p>Parsed Deobfuscated Color: ${escapeHtml(round.llm2_conversation.parsed_deobfuscated_color)} (Correct: ${round.llm2_conversation.is_correct_deobfuscation})</p>`;
                detailsHtml += `</div>`;
            }
            
            detailsHtml += `<div><strong>LLM3 (Attacker) Attempts:</strong>`;
            if (round.llm3_attempts && round.llm3_attempts.length > 0) {
                round.llm3_attempts.forEach(attempt => {
                    detailsHtml += `<div class="llm3-attempt">`;
                    detailsHtml += `<strong>Attempt ${attempt.attempt_number}</strong>`;
                    detailsHtml += `<p>Instructions Provided: ${Math.round(attempt.instructions_provided_percentage * 100)}%</p>`;
                    detailsHtml += `<p>Prompt:</p><pre>${escapeHtml(attempt.prompt)}</pre>`;
                    detailsHtml += `<p>Response:</p><pre>${escapeHtml(attempt.response)}</pre>`;
                    detailsHtml += `<p>Guessed Color: ${escapeHtml(attempt.guessed_color)} (Correct: ${attempt.is_correct})</p>`;
                    detailsHtml += `</div>`;
                });
            } else {
                detailsHtml += `<p>No attempts recorded for LLM3 or LLM1 failed.</p>`;
            }
            detailsHtml += `</div>`;
            detailsHtml += `<p>Attacker Succeeded on Attempt: ${round.attacker_succeeded_on_attempt || 'N/A (Failed or LLM1 error)'}</p>`;
            detailsHtml += `</div>`; // end round-details
        });

        battleDetailsContentDiv.innerHTML = detailsHtml;
    }

    async function init() {
        const battles = await fetchData();
        if (battles.length > 0) {
            const eloScores = calculateElo(battles);
            displayEloTable(eloScores);
            displayBattleList(battles, battles); // Pass battles twice initially, second is for details lookup
        } else {
            // Display empty state for tables/lists if no data
            displayEloTable({});
            displayBattleList([], []);
            battleDetailsContentDiv.innerHTML = '<p>No battle data found. Run the Python backend script (benchmark.py) to generate data, then refresh this page.</p>';
        }
    }

    init();
});
