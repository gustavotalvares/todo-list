const body = document.querySelector('body');
const divTasks = document.getElementById('tasks');
const divModalBackground = document.getElementById('modalBackground');
const divTaskEditor = document.getElementById('taskEditor');
const btnModalClose = document.getElementById('modalClose');
const inputModalTaskTitle = document.getElementById('editTaskTitle');
const btnTags = document.getElementById('tags');
const divTagsDropdown = document.getElementById('tagsDropdown');
const divTagsColorPalette = document.getElementById('colorPalette');

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

function openModal(event) {
  const selectedTask = event.currentTarget.parentElement.parentElement;
  const title = selectedTask.children[1].firstElementChild.firstElementChild;
  inputModalTaskTitle.value = title.innerText;
  console.log(title);
  divModalBackground.classList.remove('hidden');
  divModalBackground.classList.add('flex');
}

function addTask(title) {
  // Cria a div da nova tarefa e adiciona suas classes
  const divNewTask = document.createElement('div');
  divNewTask.classList.add(...'container mb-3 min-h-1 bg-slate-100 shadow-sm shadow-slate-300 hover:shadow-slate-400 hover:scale-[1.01] transition-all duration-200 rounded-md overflow-hidden flex'.split(' '))
  
  // Cria a div dos botões à esquerda e adiciona suas classes
  const divLeftButtons = document.createElement('div');
  divLeftButtons.classList.add(...'w-14 divide-y h-auto bg-slate-100 border-r border-slate-200 flex-shrink-0 flex-grow-0'.split(' '))

  // Cria a div do botão de editar, adiciona suas classes e ícone e insere a divLeftButtons
  const divEditButton = document.createElement('div');
  divEditButton.classList.add(...'group h-1/2 w-full flex justify-center items-center hover:bg-slate-200'.split(' '))
  divEditButton.innerHTML = icons.editIcon;
  divLeftButtons.appendChild(divEditButton);
  // Adiciona o eventListener do botão
  divEditButton.addEventListener('click', openModal);


  // Cria a div do botão de deletar, adiciona suas classes e ícone e insere a divLeftButtons
  const divDeleteButton = document.createElement('div');
  divDeleteButton.classList.add(...'group h-1/2 w-full flex justify-center items-center hover:bg-slate-200'.split(' '))
  divDeleteButton.innerHTML = icons.deleteIcon;
  divLeftButtons.appendChild(divDeleteButton);

  // Insere divLeftButtons a divNewTask
  divNewTask.appendChild(divLeftButtons);

  // Cria div da area que apresenta as informações da tarefa
  const divInfos = document.createElement('div');
  divInfos.classList.add(...'container px-4 py-3 gap-1 flex flex-col justify-center items-start'.split(' '));

  // Cria a div que contem o título da tarefa
  const divTitle = document.createElement('div');
  divTitle.classList.add(...'container flex items-center'.split(' '))

  // Cria o p que contém o título da tarefa
  const pTitle = document.createElement('p');
  pTitle.classList.add(...'text-2xl text-left mr-3'.split(' '))
  pTitle.textContent = title;

  // popula divInfos e adiciona à divNewTask
  divTitle.appendChild(pTitle);
  divInfos.appendChild(divTitle);
  divNewTask.appendChild(divInfos);

  // Cria a div que contém o botão à direita
  const divRightButton = document.createElement('div');
  divRightButton.classList.add(...'group border-l border-l-slate-200 hover:bg-slate-200 container flex flex-col items-end justify-center px-4 flex-grow-0 w-min flex-shrink-0'.split(' '));

  // Cria o botão à direita
  const divCheckButton = document.createElement('div');
  divCheckButton.classList.add(...'flex justify-center'.split(' '))
  divCheckButton.innerHTML = icons.checkIcon;

  // Adiciona a div com o botão à direita a divNewTask
  divRightButton.appendChild(divCheckButton);
  divNewTask.appendChild(divRightButton);

  // Adiciona a divNewTask à divTasks
  divTasks.appendChild(divNewTask);
}

function closeModal() {
  divModalBackground.classList.remove('flex');
  divModalBackground.classList.add('hidden');
}

function openTags() {
  divTagsDropdown.classList.remove('hidden');
  divTagsDropdown.classList.add('flex');
}

function closeTags(e) {
  if (!btnTags.contains(e.target)){
    divTagsDropdown.classList.remove('flex');
    divTagsDropdown.classList.add('hidden');
  } else {
    
  }
}

window.onload = () => {
  addTask('Título da tarefa');
  btnModalClose.addEventListener('click', closeModal);
  // btnTags.addEventListener('click', switchTags);
  divTagsDropdown.addEventListener('click', (e) => {
    e.stopImmediatePropagation();
  })
  btnTags.addEventListener('focusin', openTags);
  btnTags.addEventListener('focusout', closeTags);
}