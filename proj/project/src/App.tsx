import { NewProject } from './pages/NewProject';
import { Navigation } from './components/Navigation';

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <main className="px-8 py-8">
        <NewProject onBack={() => {}} onProjectCreated={() => {}} />
      </main>
    </div>
  );
}

export default App;