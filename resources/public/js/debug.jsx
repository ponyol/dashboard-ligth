// resources/public/js/debug.jsx
console.log("Debug script loaded");

function DebugComponent() {
  return <div className="p-10 bg-blue-500 text-white font-bold">Тестовый компонент работает!</div>;
}

// Попробуем отрендерить этот простой компонент
document.addEventListener('DOMContentLoaded', () => {
  console.log("DOM загружен, пытаемся рендерить");
  ReactDOM.render(<DebugComponent />, document.getElementById('root'));
});
