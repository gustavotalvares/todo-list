const body = document.querySelector('body');
const inputNewTask = document.getElementById('newTaskInput');
const divTasks = document.getElementById('tasks');
const divModal = document.getElementById('modal');
const modalWindow = document.getElementById('modalWindow');
const modalClose = document.getElementById('modalClose');
const modalTaskTitle = document.getElementById('modalTaskTitle');
const modalTaskDescription = document.getElementById('modalTaskDescription');
const modalTaskDate = document.getElementById('modalTaskDate');
const modalTaskTime = document.getElementById('modalTaskTime');
const modalBtnConfirma = document.getElementById('modalBtnConfirma');
const modalDeleteTask = document.getElementById('modalDeleteTask');

let currentTask;

// HTML dos icons
const icons = {
  editIcon: `
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" class="stroke-1 group-hover:stroke-[1.5] w-6 h-6">
    <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
  </svg>`,
  deleteIcon: `
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" class="stroke-1 group-hover:stroke-[1.5] w-6 h-6">
    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
  </svg>`,
  checkIcon: `
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" class="stroke-1 group-hover:stroke-[1.5] w-8 h-8">
    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>`
}

function preencheModal(task) {
  modalTaskTitle.value = task.title;
  modalTaskDescription.value = task.description;
  const amd = task.date.split('/').reverse();
  modalTaskDate.value = amd.join('-')
  modalTaskTime.value = task.time;
}

function openModal(task) {
  currentTask = task;
  preencheModal(task);
  divModal.classList.remove('hidden');
  divModal.classList.add('flex');
}

function closeModal() {
  divModal.classList.remove('flex');
  divModal.classList.add('hidden');
}

function deleteTask(task) {
  divTasks.removeChild(task.divTask);
}

function updateTaskTitle(task, newTitle) {
  task.title = newTitle;
  task.pTitle.textContent = newTitle;
}

function updateTaskDescription(task, newDescription = '') {
  if (newDescription) {
    task.pDescription.classList.remove('hidden');
  } else {
    task.pDescription.classList.add('hidden');
  }
  task.description = newDescription;
  task.pDescription.textContent = newDescription;
}

function updateTaskDate(task, newDate = '') {
  task.date = newDate;
}

function updateTaskTime(task, newTime = '') {
  task.time = newTime;
}

function updateTaskDateTime(task){
  task.pDateTime.textContent = `${task.date ? task.date : ''}${(task.date && task.time) ? ' - ' : ''}${task.time ? task.time : ''}`;
  if (task.pDateTime.textContent === '') {
    task.pDateTime.classList.add('hidden');
  } else {
    task.pDateTime.classList.remove('hidden');
  }
}

function addTask(title) {
  const task = {}
  task.title = title;
  task.description = '';
  task.date = '';
  task.time = '';

  // Cria a div da nova tarefa e adiciona suas classes
  task.divTask = document.createElement('div');
  task.divTask.classList.add(...'container mb-3 min-h-1 bg-slate-100 shadow-sm shadow-slate-300 hover:shadow-slate-400 hover:scale-[1.01] transition-all duration-200 rounded-md overflow-hidden flex'.split(' '))
  
  // Cria a div dos botões à esquerda e adiciona suas classes
  task.divLeftButtons = document.createElement('div');
  task.divLeftButtons.classList.add(...'w-14 divide-y h-auto bg-slate-100 border-r border-slate-200 flex-shrink-0 flex-grow-0'.split(' '))

  // Cria a div do botão de editar, adiciona suas classes e ícone e insere a divLeftButtons
  task.divEditButton = document.createElement('div');
  task.divEditButton.classList.add(...'group h-1/2 w-full flex justify-center items-center hover:bg-slate-200'.split(' '))
  task.divEditButton.innerHTML = icons.editIcon;
  task.divLeftButtons.appendChild(task.divEditButton);

  // Cria a div do botão de deletar, adiciona suas classes e ícone e insere a divLeftButtons
  task.divDeleteButton = document.createElement('div');
  task.divDeleteButton.classList.add(...'group h-1/2 w-full flex justify-center items-center hover:bg-slate-200'.split(' '))
  task.divDeleteButton.innerHTML = icons.deleteIcon;
  task.divLeftButtons.appendChild(task.divDeleteButton);

  // Insere divLeftButtons a divTask
  task.divTask.appendChild(task.divLeftButtons);

  // Cria div da area que apresenta as informações da tarefa
  task.divInfos = document.createElement('div');
  task.divInfos.classList.add(...'container px-4 py-3 gap-1 flex flex-col justify-center items-start'.split(' '));

  // Cria a div que contem o título da tarefa
  task.divTitle = document.createElement('div');
  task.divTitle.classList.add(...'container flex items-center'.split(' '))

  // Cria o p que contém o título da tarefa
  task.pTitle = document.createElement('p');
  task.pTitle.classList.add(...'text-2xl text-left mr-3'.split(' '))
  task.pTitle.textContent = task.title;

  // Cria o p que contém a descrição
  task.pDescription = document.createElement('p');
  task.pDescription.classList.add(...'text-sm text-left text-slate-500'.split(' '));
  task.pDescription.textContent = task.description;
  if (task.description === '') {
    task.pDescription.classList.add('hidden');
  }

  // Cria o p que contém data e hora da task
  task.pDateTime = document.createElement('p');
  task.pDateTime.classList.add(...'text-xs text-left text-slate-500 pt-3'.split(' '));
  task.pDateTime.textContent = `${task.date ? task.date : ''}${(task.date && task.time) ? ' - ' : ''}${task.time ? task.time : ''}`;
  if (task.pDateTime.textContent === '') {
    task.pDateTime.classList.add('hidden');
  }

  // popula divInfos e adiciona à divTask
  task.divTitle.appendChild(task.pTitle);
  task.divInfos.appendChild(task.divTitle);
  task.divInfos.appendChild(task.pDescription);
  task.divInfos.appendChild(task.pDateTime);
  task.divTask.appendChild(task.divInfos);

  // Cria a div que contém o botão à direita
  task.divRightButton = document.createElement('div');
  task.divRightButton.classList.add(...'group border-l border-l-slate-200 hover:bg-slate-200 container flex flex-col items-end justify-center px-4 flex-grow-0 w-min flex-shrink-0'.split(' '));

  // Cria o botão à direita
  task.divCheckButton = document.createElement('div');
  task.divCheckButton.classList.add(...'flex justify-center'.split(' '))
  task.divCheckButton.innerHTML = icons.checkIcon;

  // Adiciona a div com o botão à direita a divTask
  task.divRightButton.appendChild(task.divCheckButton);
  task.divTask.appendChild(task.divRightButton);

  // Adiciona o eventListener da task
  task.divTask.addEventListener('click', (e) => {
    if (task.divEditButton.contains(e.target)) {
      openModal(task);
    }

    if (task.divDeleteButton.contains(e.target)) {
      deleteTask(task)
    }
  });

  // Adiciona a divTask à divTasks
  divTasks.appendChild(task.divTask);
}

function modalConfirma(){
  if(modalTaskTitle.value !== '') {
    updateTaskTitle(currentTask, modalTaskTitle.value);
    updateTaskDescription(currentTask, modalTaskDescription.value);
    const dma = modalTaskDate.value.split('-').reverse();
    updateTaskDate(currentTask, dma.join('/'));
    updateTaskTime(currentTask, modalTaskTime.value);
    updateTaskDateTime(currentTask);
    closeModal();
  }
}

divModal.addEventListener('click', (e) => {
  if (!modalWindow.contains(e.target) || modalClose.contains(e.target)) {
    closeModal();
  }

  if (modalBtnConfirma.contains(e.target)) {
    modalConfirma();
  }

  if (modalDeleteTask.contains(e.target)) {
    deleteTask(currentTask);
    closeModal();
  }
})

divModal.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    modalConfirma();
  }
})

window.onload = () => {
  addTask('Título da tarefa');
  inputNewTask.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && inputNewTask.value !== '') {
      addTask(inputNewTask.value);
      inputNewTask.value = '';
    }
  })
}