export function runTest() {
  console.log('TestImport.tsx loaded and runTest called');
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML += '<br><h2 style="color: blue;">Dynamic import works!</h2>';
  }
}