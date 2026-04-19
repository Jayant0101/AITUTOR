import { UserTier } from './saas/tiers';

export interface User {
  id: string;
  email?: string;
  user_metadata?: {
    display_name?: string;
    avatar_url?: string;
  };
}

export interface Todo {
  id: string;
  name: string;
  is_completed: boolean;
  created_at: string;
  user_id: string;
}

export interface QuizQuestion {
  question: string;
  options: Record<string, string>;
  correct_answer?: string;
  explanation?: string;
}

export interface QuizData {
  quiz_id: string;
  topic: string;
  difficulty: string;
  questions: QuizQuestion[];
}

export interface QuizResult {
  quiz_id: string;
  topic: string;
  difficulty: string;
  score: number;
  total_questions: number;
  correct_count: number;
  time_taken: number;
  feedback?: string;
}

export interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  isMobile: boolean;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

export interface Message {
  id: number | string;
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface YouTubeResult {
  id: string;
  title: string;
  thumbnail: string;
  channel: string;
  url: string;
}
