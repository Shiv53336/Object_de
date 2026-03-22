import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  DEFAULT_CATEGORIES, DEFAULT_BUDGET, KEYS,
} from '../constants';
import { todayStr, yesterdayStr } from '../utils/helpers';

const AppContext = createContext(null);

// ─── Async storage hook ────────────────────────────────────────────────────────
function useStorage(key, initial) {
  const [value, setValue] = useState(initial);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(key).then(raw => {
      if (raw !== null) {
        try { setValue(JSON.parse(raw)); } catch (_) {}
      }
      setReady(true);
    });
  }, [key]);

  const set = useCallback((valOrFn) => {
    setValue(prev => {
      const next = typeof valOrFn === 'function' ? valOrFn(prev) : valOrFn;
      AsyncStorage.setItem(key, JSON.stringify(next));
      return next;
    });
  }, [key]);

  return [value, set, ready];
}

// ─── Provider ─────────────────────────────────────────────────────────────────
export function AppProvider({ children }) {
  const [currency,   setCurrency,   r1] = useStorage(KEYS.currency,   '₹');
  const [budget,     setBudget,     r2] = useStorage(KEYS.budget,     DEFAULT_BUDGET);
  const [expenses,   setExpenses,   r3] = useStorage(KEYS.expenses,   []);
  const [categories, setCategories, r4] = useStorage(KEYS.categories, DEFAULT_CATEGORIES);
  const [recurring,  setRecurring,  r5] = useStorage(KEYS.recurring,  []);
  const [dailyNotes, setDailyNotes, r6] = useStorage(KEYS.dailyNotes, {});
  const [streak,     setStreak,     r7] = useStorage(KEYS.streak,     {
    currentStreak: 0, longestStreak: 0, lastLogDate: null,
  });

  const ready = r1 && r2 && r3 && r4 && r5 && r6 && r7;

  // ── On first load: check streak + process recurring ──────────────────────
  useEffect(() => {
    if (!ready) return;

    // Break streak if missed a day
    setStreak(prev => {
      if (prev.lastLogDate && prev.lastLogDate < yesterdayStr()) {
        return { ...prev, currentStreak: 0 };
      }
      return prev;
    });

    // Auto-add due recurring expenses
    const today = todayStr();
    const toAdd = [];
    const updatedIds = [];

    recurring.forEach(r => {
      if (!r.active || r.lastAdded === today) return;
      const isDue = () => {
        if (r.frequency === 'daily')   return true;
        if (r.frequency === 'weekly')  return new Date().getDay() === 1;
        if (r.frequency === 'monthly') return new Date().getDate() === r.dayOfMonth;
        if (r.frequency === 'yearly')  return new Date().getMonth() === 0 && new Date().getDate() === 1;
        return false;
      };
      if (isDue()) {
        toAdd.push({
          id: Date.now() + Math.random(),
          amount: r.amount, category: r.category, note: r.note,
          date: today, emoji: r.emoji, payment: r.payment, type: 'expense',
        });
        updatedIds.push(r.id);
      }
    });

    if (toAdd.length > 0) {
      setExpenses(prev => [...toAdd, ...prev]);
      setRecurring(prev => prev.map(r =>
        updatedIds.includes(r.id) ? { ...r, lastAdded: today } : r
      ));
    }
  }, [ready]);

  // ── Streak update ─────────────────────────────────────────────────────────
  const updateStreak = useCallback(() => {
    const today = todayStr();
    setStreak(prev => {
      if (prev.lastLogDate === today) return prev;
      const cont      = prev.lastLogDate === yesterdayStr();
      const newStreak = cont ? prev.currentStreak + 1 : 1;
      return {
        currentStreak: newStreak,
        longestStreak: Math.max(newStreak, prev.longestStreak),
        lastLogDate:   today,
      };
    });
  }, [setStreak]);

  // ── CRUD helpers ──────────────────────────────────────────────────────────
  const addExpense  = useCallback((exp) => {
    setExpenses(prev => [exp, ...prev]);
    updateStreak();
  }, [setExpenses, updateStreak]);

  const deleteExpense = useCallback((id) =>
    setExpenses(prev => prev.filter(e => e.id !== id)), [setExpenses]);

  const editExpense = useCallback((updated) =>
    setExpenses(prev => prev.map(e => e.id === updated.id ? updated : e)), [setExpenses]);

  const addCategory = useCallback((cat) =>
    setCategories(prev => [...prev, cat]), [setCategories]);

  const saveNote = useCallback((date, note) =>
    setDailyNotes(prev => ({ ...prev, [date]: note })), [setDailyNotes]);

  const addRecurring    = useCallback((r) => setRecurring(prev => [...prev, r]), [setRecurring]);
  const toggleRecurring = useCallback((id) =>
    setRecurring(prev => prev.map(r => r.id === id ? { ...r, active: !r.active } : r)), [setRecurring]);
  const deleteRecurring = useCallback((id) =>
    setRecurring(prev => prev.filter(r => r.id !== id)), [setRecurring]);

  const clearAll = useCallback(() =>
    setExpenses([]), [setExpenses]);

  const value = {
    // state
    currency, setCurrency,
    budget, setBudget,
    expenses,
    categories,
    recurring,
    dailyNotes,
    streak,
    ready,
    // actions
    addExpense, deleteExpense, editExpense,
    addCategory,
    saveNote,
    addRecurring, toggleRecurring, deleteRecurring,
    clearAll,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be inside AppProvider');
  return ctx;
}
