import { Zap } from 'lucide-react';

export function Navigation() {
  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-blue-600 to-blue-700 rounded-lg">
              <Zap className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">UMA</h1>
              <p className="text-xs text-gray-500">Universal Multi-Agent Upgrader</p>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}