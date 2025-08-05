document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const subjectSelect = document.getElementById('subject-select');
    const gradeSelect = document.getElementById('grade-select');
    const strandSelect = document.getElementById('strand-select');
    const substrandSelect = document.getElementById('substrand-select');
    const numQuestionsInput = document.getElementById('num-questions');
    const questionTypeSelect = document.getElementById('question-type');
    const generateButton = document.getElementById('generate-button');
    const questionsOutput = document.getElementById('questions-output');
    const loadingIndicator = document.getElementById('loading-indicator');
    const generationErrorDiv = document.getElementById('error-message-generation');

    // --- Global variables to store state ---
    let generatedQuestionsData = [];
    let selectedLearningOutcomeId = null; 

    // --- Helper Functions ---
    async function fetchData(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) {
            generationErrorDiv.textContent = `Failed to load data. Please check network connection.`;
            generationErrorDiv.classList.remove('hidden');
            return null;
        }
    }

    function populateDropdown(selectElement, items, defaultOptionText, valueField = 'id', nameField = 'name') {
        selectElement.innerHTML = `<option value="">-- ${defaultOptionText} --</option>`;
        if (items && items.length > 0) {
            items.forEach(item => {
                const option = document.createElement('option');
                option.value = item[valueField];
                option.textContent = item[nameField];
                selectElement.appendChild(option);
            });
            selectElement.disabled = false;
        } else {
            selectElement.disabled = true;
        }
    }

    function resetDropdowns(...dropdowns) {
        dropdowns.forEach(dd => {
            dd.innerHTML = `<option value="">-- Select --</option>`;
            dd.disabled = true;
        });
        generateButton.disabled = true;
        selectedLearningOutcomeId = null; 
        questionsOutput.innerHTML = '<p class="text-gray-500">Select curriculum details to begin.</p>';
        generationErrorDiv.classList.add('hidden');
    }

    // --- Event Listeners ---
    subjectSelect.addEventListener('change', async () => {
        resetDropdowns(gradeSelect, strandSelect, substrandSelect);
        if (subjectSelect.value) {
            const grades = await fetchData('/api/grades');
            if (grades) populateDropdown(gradeSelect, grades, "Select Grade");
        }
    });

    gradeSelect.addEventListener('change', async () => {
        resetDropdowns(strandSelect, substrandSelect);
        if (subjectSelect.value && gradeSelect.value) {
            const strands = await fetchData(`/api/strands?subject_id=${subjectSelect.value}&grade_id=${gradeSelect.value}`);
            if (strands) populateDropdown(strandSelect, strands, "Select Strand");
        }
    });

    strandSelect.addEventListener('change', async () => {
        resetDropdowns(substrandSelect);
        if (strandSelect.value) {
            const substrands = await fetchData(`/api/substrands?strand_id=${strandSelect.value}`);
            if (substrands) populateDropdown(substrandSelect, substrands, "Select Sub-Strand");
        }
    });

    substrandSelect.addEventListener('change', async () => {
        generateButton.disabled = true;
        selectedLearningOutcomeId = null;
        generationErrorDiv.classList.add('hidden');

        if (substrandSelect.value) {
            const learningOutcomes = await fetchData(`/api/learning_outcomes?substrand_id=${substrandSelect.value}`);
            
            if (learningOutcomes && learningOutcomes.length > 0) {
                const firstId = learningOutcomes[0].id;

                if (firstId && typeof firstId === 'number') {
                    selectedLearningOutcomeId = firstId;
                    generateButton.disabled = false;
                } else {
                    generationErrorDiv.textContent = 'Error: Curriculum data is invalid. Please try another selection.';
                    generationErrorDiv.classList.remove('hidden');
                }
            } else {
                generationErrorDiv.textContent = 'No learning outcomes found for this sub-strand. Please select another.';
                generationErrorDiv.classList.remove('hidden');
            }
        }
    });

    generateButton.addEventListener('click', async () => {
        if (!selectedLearningOutcomeId || typeof selectedLearningOutcomeId !== 'number') {
            alert(`Cannot generate questions. The Learning Outcome ID is invalid. Please re-select the Sub-Strand.`);
            return;
        }

        loadingIndicator.classList.remove('hidden');
        questionsOutput.innerHTML = '';
        generateButton.disabled = true;

        const payload = {
            learning_outcome_id: selectedLearningOutcomeId,
            num_questions: parseInt(numQuestionsInput.value),
            question_type: questionTypeSelect.value,
        };

        try {
            const response = await fetch('/api/questions/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'An unknown server error occurred.');
            }
            generatedQuestionsData = data;
            renderQuestions(generatedQuestionsData);
        } catch (error) {
            generationErrorDiv.textContent = error.message;
            generationErrorDiv.classList.remove('hidden');
        } finally {
            loadingIndicator.classList.add('hidden');
            if (selectedLearningOutcomeId) {
                generateButton.disabled = false;
            }
        }
    });
    
    // NOTE: Your download and render functions need to be added back here if you use them
    function renderQuestions(questions) {
        // Your logic to display questions
    }
});